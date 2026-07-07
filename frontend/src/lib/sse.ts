/**
 * Resilient Server-Sent Events client with bounded retries + fallback poll.
 *
 * Lifted from ScanWalkthroughPage.tsx so every SSE consumer in Daena
 * (chat, scans, cron lifecycle, queue lifecycle, approvals, pipeline)
 * shares one battle-tested reconnect strategy.
 *
 * Behavior
 * --------
 * - Subscribe via fetch + ReadableStream so the JWT bearer token can be
 *   sent as an Authorization header (EventSource cannot set headers).
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
 * - Auth: sends the JWT bearer token from localStorage as a fetch
 *   Authorization header. EventSource could not (no header API), which
 *   401'd every authed stream. The token never goes in the URL, so it
 *   does not leak to access logs / referer / DevTools.
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
    onEvent,
    onError,
    onReconnecting,
    fallbackPoll,
  } = opts

  const [status, setStatus] = useState<SSEStatus>('connecting')
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  // Refs let us mutate state from inside the EventSource callbacks
  // without triggering re-renders (which would re-fire the effect).
  const abortRef = useRef<AbortController | null>(null)
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
    attemptRef.current = 0
    // Per-run cancellation flag. A ref shared across effect runs races
    // with React 19 StrictMode's mount/cleanup/mount cycle: run 1's
    // aborted fetch would observe the flag already reset by run 2 and
    // spuriously reconnect. A local closes over THIS run only.
    let stopped = false

    // Empty url = consumer opted out (e.g. stream disabled). Stay idle
    // instead of firing a bogus request.
    if (!url) {
      setStatus('closed')
      return () => {
        stopped = true
      }
    }

    const controller = new AbortController()
    abortRef.current = controller

    // Parse complete SSE frames out of a rolling buffer and forward each
    // to the consumer. A frame is the text between blank lines; its
    // ``event:`` line sets the type, ``data:`` lines the payload.
    const dispatchFrames = (frames: string[]) => {
      for (const frame of frames) {
        if (!frame.trim()) continue
        let frameType = 'message'
        let frameData = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) {
            frameType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            frameData += (frameData ? '\n' : '') + line.replace(/^data:\s?/, '')
          }
          // ':' comment / heartbeat lines are ignored.
        }
        if (!frameData) continue
        let parsed: unknown = frameData
        try {
          parsed = JSON.parse(frameData)
        } catch {
          // Not JSON -- forward the raw string so consumers can decide.
        }
        if (!stopped) onEventRef.current({ type: frameType, data: parsed })
      }
    }

    const scheduleReconnect = () => {
      if (stopped) return
      if (attemptRef.current < maxRetries) {
        const next = attemptRef.current + 1
        attemptRef.current = next
        setReconnectAttempt(next)
        setStatus('reconnecting')
        onReconnectingRef.current?.(next, maxRetries)
        const delayMs = Math.min(initialBackoffMs * 2 ** (next - 1), maxBackoffMs)
        reconnectTimerRef.current = setTimeout(() => {
          void connect()
        }, delayMs)
      } else {
        // Retries exhausted: flip to fallback + let the consumer pull a
        // REST snapshot once. We do NOT retry forever (masks outages).
        setStatus('fallback')
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

    // Fetch-based SSE so we can send the JWT bearer token (EventSource
    // cannot set headers). Reconnects on error AND on clean EOF (server
    // restart / proxy timeout), matching EventSource semantics, with the
    // same bounded backoff: 1s -> 2s -> 4s -> 8s -> 15s.
    const connect = async () => {
      if (stopped) return
      let response: Response
      try {
        const token = localStorage.getItem('daena_token')
        response = await fetch(url, {
          method: 'GET',
          headers: {
            Accept: 'text/event-stream',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          credentials: withCredentials ? 'include' : 'same-origin',
          signal: controller.signal,
        })
      } catch (err) {
        if (stopped) return
        onErrorRef.current?.(err)
        scheduleReconnect()
        return
      }

      if (!response.ok || !response.body) {
        if (stopped) return
        onErrorRef.current?.(new Error(`SSE open failed: ${response.status}`))
        scheduleReconnect()
        return
      }

      attemptRef.current = 0
      if (!stopped) {
        setReconnectAttempt(0)
        setStatus('connected')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      try {
        while (true) {
          if (stopped) {
            try { await reader.cancel() } catch { /* ignore */ }
            return
          }
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          // SSE frames end with a blank line. Keep the trailing partial
          // frame in the buffer for the next read.
          const frames = buffer.split('\n\n')
          buffer = frames.pop() ?? ''
          dispatchFrames(frames)
        }
      } catch (err) {
        if (stopped) return
        onErrorRef.current?.(err)
        scheduleReconnect()
        return
      }

      // Clean EOF: reconnect like EventSource would on a dropped stream.
      if (!stopped) scheduleReconnect()
    }

    setStatus('connecting')
    void connect()

    return () => {
      stopped = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      abortRef.current?.abort()
      abortRef.current = null
      setStatus('closed')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, withCredentials, maxRetries, initialBackoffMs, maxBackoffMs])

  return {
    status,
    reconnectAttempt,
    close: () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      abortRef.current?.abort()
      abortRef.current = null
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
  /**
   * Fired once each time the HTTP stream is successfully (re)established
   * (response.ok with a readable body), BEFORE any bytes are read. Lets a
   * caller flip an honest "connected/live" flag at the exact transport
   * moment instead of waiting for the first data frame (Rule 17). Optional,
   * so existing callers are unaffected.
   */
  onOpen?: () => void
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
  /**
   * Treat a clean EOF (the server closing the response body) as a dropped
   * connection and reconnect, instead of returning. OFF by default so a
   * finite/one-shot stream still completes on EOF. A PERSISTENT doorbell
   * stream (e.g. the Mission Control graph channel) sets this true so a
   * graceful backend restart or a proxy recycling the idle connection
   * re-establishes the stream rather than silently dropping to polling.
   * Mirrors ``useResilientSSE``, which already reconnects on clean EOF.
   */
  reconnectOnClose?: boolean
}

/**
 * Fetch-based SSE consumer with bounded retries.
 *
 * Returns when the underlying body is exhausted, the abort signal
 * fires, or retries are exhausted. Domain code is responsible for
 * deciding what "stream complete" means via its own event types
 * (e.g. ``finalize``, ``done``). This helper does not try to parse
 * domain semantics; it only manages the transport. Set
 * ``reconnectOnClose`` for a persistent stream that should re-establish
 * (not return) when the server closes the body.
 */
export async function streamWithRetry(
  opts: StreamWithRetryOptions,
): Promise<void> {
  const {
    open,
    onEvent,
    onOpen,
    maxRetries = 5,
    initialBackoffMs = 1000,
    maxBackoffMs = 15000,
    onReconnecting,
    signal,
    reconnectOnClose = false,
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
    // Transport is established (response.ok + readable body). Signal the
    // caller now so an honest "live" flag flips at connect, not on the
    // first frame (which for a low-traffic stream could be 25s away).
    onOpen?.()

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
        if (done) {
          // Clean EOF (server closed the body). For a one-shot stream the
          // closed body means "complete" and we return. For a persistent
          // doorbell stream (reconnectOnClose) a graceful restart or a
          // proxy recycling the connection must reconnect, not drop -- so
          // route it through the same bounded backoff as a transport error.
          if (!reconnectOnClose || signal?.aborted) return
          attempt += 1
          if (attempt > maxRetries) return
          onReconnecting?.(attempt, maxRetries)
          await new Promise((r) =>
            setTimeout(r, Math.min(initialBackoffMs * 2 ** (attempt - 1), maxBackoffMs)),
          )
          break
        }

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

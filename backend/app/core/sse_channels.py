"""Lightweight per-channel async pub/sub for SSE fanout.

Each ``SSEChannel`` is an in-process broadcast bus. Producers call
``publish(event_type, data)`` and any number of subscribers consume the
events as an async iterator (suitable for FastAPI ``StreamingResponse``).

Design goals
------------
- Stdlib only. No Redis. No PubSub. No new dependencies.
- Per-subscriber bounded ``asyncio.Queue`` so a slow client never holds
  publishers back. If a queue saturates, the OLDEST event is dropped on
  that subscriber's queue and a synthetic ``channel.dropped`` event is
  appended. Other subscribers are unaffected.
- Subscriber lifetimes are scoped to the calling coroutine. The
  ``subscribe()`` async generator runs a ``finally`` block that detaches
  the queue when the consumer cancels (client disconnect, timeout, etc.)
- Heartbeats: subscribers receive a synthetic ``ping`` envelope every
  ``HEARTBEAT_SECONDS`` of idle time so the FastAPI route can serialize
  it as an SSE comment line, keeping proxies (nginx, Cloud Run frontend,
  Cloudflare) from idling the connection.
- Module-level singletons for the four channels Daena needs today
  (``cron``, ``queue``, ``approvals``, ``pipeline``). Importing this
  module is enough to wire publishers to the channels; routes import
  the channel and call ``subscribe()`` without further setup.

Scope guard
-----------
This module is BACKEND-PATH ONLY. It must never be imported on the
WorldSignal hot path (deterministic, no LLM, no async pubsub). Daena's
governance / cron / queue / pipeline planes are async and benefit from
fan-out; WorldSignal is not.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Per-subscriber buffer. Event objects are tiny dicts so 1000 is generous;
# at 100 events/sec a slow client gets 10 seconds of headroom before drops
# kick in. Adjust here if a chatty channel surfaces.
MAX_BUFFER_PER_SUBSCRIBER = 1000

# How long an idle subscriber waits before the channel emits a synthetic
# ``ping`` envelope. 25 seconds keeps under the typical 30s nginx idle
# timeout. Heartbeat events are ignored by domain code; they only exist
# so the SSE route can serialize a comment line and keep the TCP
# connection from being reaped by upstream proxies.
HEARTBEAT_SECONDS = 25.0


class SSEChannel:
    """A broadcast async pub/sub bus for a single logical channel.

    One channel per domain (cron, queue, approvals, pipeline). Publishers
    don't know about subscribers; subscribers don't know about other
    subscribers. The channel mediates everything via per-consumer
    ``asyncio.Queue`` instances kept inside the channel.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Logical channel name (used in logs and the heartbeat envelope)."""
        return self._name

    def subscriber_count(self) -> int:
        """Number of active subscriber queues right now."""
        return len(self._subscribers)

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Fan an event out to every subscriber.

        Each event is wrapped into the standard envelope::

            {
                "type": event_type,
                "data": data,
                "channel": <channel name>,
                "ts": <ISO 8601 UTC timestamp>,
            }

        The envelope shape is shared with the chat SSE consumer so the
        frontend ``useResilientSSE`` hook can parse all four channels
        with one decoder.

        Slow subscribers do NOT block the publisher. If a queue is full
        we drop the oldest event on THAT queue, append a synthetic
        ``channel.dropped`` envelope so the consumer knows it lost data,
        and continue. Other subscribers are unaffected.
        """
        envelope = {
            "type": event_type,
            "data": data,
            "channel": self._name,
            "ts": datetime.now(UTC).isoformat(),
        }

        # Snapshot under lock so a concurrent unsubscribe doesn't surface
        # a discarded queue mid-iteration. Lock is released before the
        # actual put so a slow subscriber cannot wedge subscribe()
        # callers that are waiting to register.
        async with self._lock:
            queues = list(self._subscribers)

        for queue in queues:
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # Drop the oldest event to make room, then signal the
                # drop to the consumer. We don't block on get_nowait
                # because the queue is bounded -- a single attempt is
                # enough to free one slot.
                try:
                    queue.get_nowait()
                    queue.put_nowait({
                        "type": "channel.dropped",
                        "data": {
                            "reason": "subscriber_buffer_full",
                            "dropped_event": event_type,
                        },
                        "channel": self._name,
                        "ts": datetime.now(UTC).isoformat(),
                    })
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    # Race -- another publish drained or refilled the
                    # queue between our two ops. The consumer will see
                    # it on the next event; nothing to do here.
                    pass
                logger.warning(
                    "sse_channel.dropped_event",
                    channel=self._name,
                    event_type=event_type,
                )

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Yield envelopes for the lifetime of the consumer coroutine.

        Usage::

            async for envelope in cron_channel.subscribe():
                yield f"event: {envelope['type']}\\ndata: {json.dumps(envelope)}\\n\\n"

        The async generator deregisters its queue when the consumer
        cancels or returns, so client disconnects clean themselves up
        without a leak. If no events arrive for ``HEARTBEAT_SECONDS`` a
        synthetic ``ping`` envelope is yielded so the SSE route can keep
        the TCP connection warm.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=MAX_BUFFER_PER_SUBSCRIBER,
        )

        async with self._lock:
            self._subscribers.add(queue)

        logger.debug(
            "sse_channel.subscribed",
            channel=self._name,
            subscriber_count=self.subscriber_count(),
        )

        try:
            while True:
                try:
                    envelope = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield {
                        "type": "ping",
                        "data": {"channel": self._name},
                        "channel": self._name,
                        "ts": datetime.now(UTC).isoformat(),
                    }
                    continue
                yield envelope
        finally:
            async with self._lock:
                self._subscribers.discard(queue)
            logger.debug(
                "sse_channel.unsubscribed",
                channel=self._name,
                subscriber_count=self.subscriber_count(),
            )


# ─────────────────────────────────────────────────────────────────────
# Module-level singletons
#
# Importing any of these from a producer is enough to wire the producer
# to the channel. Routes that subscribe import the same singleton.
# ─────────────────────────────────────────────────────────────────────

cron_channel = SSEChannel("cron")
queue_channel = SSEChannel("queue")
approval_channel = SSEChannel("approvals")
pipeline_channel = SSEChannel("pipeline")
# Mission Control "Brain" live channel. Carries THIN change notifications
# only: a producer publishes "graph.changed" after a task/workstream state
# moves, and the /graph/stream route fans it to the canvas, which re-fetches
# GET /graph and diffs it client-side. The projection itself is NEVER pushed
# here -- /graph stays the single source of truth, the channel is just a
# "something moved, re-pull" doorbell.
graph_channel = SSEChannel("graph")


def get_channel(name: str) -> SSEChannel | None:
    """Look up a registered channel by name. None if unknown."""
    return {
        "cron": cron_channel,
        "queue": queue_channel,
        "approvals": approval_channel,
        "pipeline": pipeline_channel,
        "graph": graph_channel,
    }.get(name)


async def publish_graph_changed(reason: str, **detail: Any) -> None:
    """Best-effort doorbell telling the live Brain the projection changed.

    A THIN signal: subscribers re-fetch GET /graph and diff it themselves,
    so the payload is just a ``reason`` plus optional debug ``detail`` --
    never the projection. Wrapped so a telemetry push can NEVER break the
    domain write that triggered it: any failure (serialization, a dead
    subscriber, cancellation during shutdown) is swallowed and logged at
    debug. Safe to fire-and-(optionally-)await from any async service after
    a state change; producers should call it best-effort and never let its
    result gate their own commit.
    """
    try:
        await graph_channel.publish("graph.changed", {"reason": reason, **detail})
    except Exception:  # noqa: BLE001 -- telemetry must never break a domain write
        logger.debug("graph_channel.publish_failed", reason=reason, exc_info=True)


# ─────────────────────────────────────────────────────────────────────
# Per-workstream channels (PR-SPINE-06, 2026-05-02)
#
# Unlike the 4 domain singletons above, workstream channels are created
# lazily per id. WorkstreamService publishes to them on every state
# change; the GET /workstreams/{id}/stream endpoint subscribes.
#
# Memory cost: ~200 bytes per empty channel. At 10k workstreams that
# is ~2MB; acceptable for v1. A janitor task that reaps channels with
# subscriber_count==0 AND a recent terminal-state observation can be
# added if memory pressure surfaces (documented as PR-SPINE-06 debt).
# ─────────────────────────────────────────────────────────────────────

_workstream_channels: dict[str, SSEChannel] = {}
_workstream_channels_lock = asyncio.Lock()


async def get_workstream_channel(workstream_id: str) -> SSEChannel:
    """Return the SSEChannel for a workstream, creating it on first use.

    Safe to call from any async context. The lock is held only on the
    miss path (channel creation), so the hot path (channel exists)
    bypasses contention.

    Channels persist for the process lifetime. See module-level comment
    for memory analysis.
    """
    ch = _workstream_channels.get(workstream_id)
    if ch is not None:
        return ch
    async with _workstream_channels_lock:
        # Re-check under the lock so two concurrent misses don't both
        # create + the loser leak orphan subscribers later.
        ch = _workstream_channels.get(workstream_id)
        if ch is None:
            ch = SSEChannel(f"workstream:{workstream_id}")
            _workstream_channels[workstream_id] = ch
        return ch


def workstream_channel_count() -> int:
    """Total registered workstream channels (alive subscribers + idle)."""
    return len(_workstream_channels)


__all__ = [
    "SSEChannel",
    "approval_channel",
    "cron_channel",
    "get_channel",
    "get_workstream_channel",
    "graph_channel",
    "pipeline_channel",
    "publish_graph_changed",
    "queue_channel",
    "workstream_channel_count",
]

"""DaenaDaemon -- background service that runs without UI.

Like OpenClaw's Gateway but governed. Runs heartbeat, processes
work queue, and sends notifications.

Usage:
    python -m app.services.agent_core.daemon start
    python -m app.services.agent_core.daemon stop
    python -m app.services.agent_core.daemon status
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

PID_FILE = Path.home() / ".daena" / "daemon.pid"
LOG_FILE = Path.home() / ".daena" / "daemon.log"


class DaenaDaemon:
    """Background Daena service -- heartbeat + work queue processing."""

    def __init__(self) -> None:
        self.running = False

    async def start(self) -> None:
        """Start the background daemon."""
        self.running = True
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        logger.info("daemon.starting", pid=os.getpid())

        # Start heartbeat
        from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon

        heartbeat = HeartbeatDaemon.get_instance()
        await heartbeat.start()

        # Main loop
        try:
            while self.running:
                # Process work queue
                await self._process_queue()
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            await heartbeat.stop()
            self._cleanup()

    async def _process_queue(self) -> None:
        """Check work queue and execute next task."""
        from app.services.heartbeat.work_queue import WorkQueue

        queue = WorkQueue.overnight_default()
        task = queue.get_next()

        if task:
            logger.info("daemon.processing_task", task_id=task.task_id, title=task.title)
            queue.mark_in_progress(task.task_id)

            try:
                from app.services.agent_core.agent_loop import AgentLoop

                loop = AgentLoop()
                async for update in loop.execute(task.prompt, {}):
                    # Log updates
                    if update.get("type") in ("agent_complete", "agent_step_failed"):
                        logger.info("daemon.task_update", **{k: str(v)[:100] for k, v in update.items()})

                receipt = loop.get_receipt()
                if receipt and receipt.get("status") == "completed":
                    queue.mark_completed(task.task_id, f"Done: {receipt['steps_completed']} steps", receipt.get("total_cost_usd", 0))
                else:
                    queue.mark_failed(task.task_id, receipt.get("status", "unknown") if receipt else "no receipt")

            except Exception as exc:
                queue.mark_failed(task.task_id, str(exc))
                logger.error("daemon.task_error", task_id=task.task_id, error=str(exc))

    def stop(self) -> None:
        """Stop the daemon."""
        self.running = False
        self._cleanup()
        logger.info("daemon.stopped")

    def _cleanup(self) -> None:
        if PID_FILE.exists():
            PID_FILE.unlink()

    @staticmethod
    def status() -> dict:
        """Check daemon status."""
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            return {"running": True, "pid": int(pid)}
        return {"running": False}


# CLI entry point
if __name__ == "__main__":
    import sys

    daemon = DaenaDaemon()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "start":
            asyncio.run(daemon.start())
        elif cmd == "stop":
            daemon.stop()
        elif cmd == "status":
            s = DaenaDaemon.status()
            if s["running"]:
                print(f"Running (PID: {s['pid']})")
            else:
                print("Not running")
    else:
        print("Usage: daemon.py [start|stop|status]")

"""Autopilot: continuation loop, criticality classification, background queue.

When Autopilot ON, Daena keeps executing plan steps without waiting for
user input. The CriticalityClassifier gates each action into AUTO_PROCEED,
NOTIFY_AFTER, or PAUSE_FOR_APPROVAL. The AutopilotController manages the
loop with kill switch, cost ceiling, and WebSocket notifications.
"""

from app.services.autopilot.background_queue import (
    BackgroundQueue,
    BackgroundTask,
)
from app.services.autopilot.continuation import (
    AutopilotController,
    AutopilotState,
)
from app.services.autopilot.criticality_classifier import (
    CriticalityClassifier,
    CriticalityLevel,
    CriticalityRule,
)

__all__ = [
    "CriticalityClassifier",
    "CriticalityLevel",
    "CriticalityRule",
    "AutopilotController",
    "AutopilotState",
    "BackgroundQueue",
    "BackgroundTask",
]

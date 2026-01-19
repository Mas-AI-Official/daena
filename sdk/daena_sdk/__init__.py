"""
Daena AI VP Python SDK

Official Python SDK for integrating with Daena AI VP System.
Provides a clean, type-safe interface to all Daena APIs.
"""

from .client import DaenaClient
from .exceptions import (
    DaenaAPIError,
    DaenaAuthenticationError,
    DaenaRateLimitError,
    DaenaNotFoundError,
    DaenaValidationError
)
from .models import (
    Agent,
    Department,
    MemoryRecord,
    CouncilDecision,
    ExperienceVector,
    SystemMetrics
)

__version__ = "1.0.0"
__all__ = [
    "DaenaClient",
    "DaenaAPIError",
    "DaenaAuthenticationError",
    "DaenaRateLimitError",
    "DaenaNotFoundError",
    "DaenaValidationError",
    "Agent",
    "Department",
    "MemoryRecord",
    "CouncilDecision",
    "ExperienceVector",
    "SystemMetrics",
]


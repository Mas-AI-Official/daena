"""
CMP Connector Ecosystem - Connected Media Protocol
Inspired by n8n connector architecture for seamless integrations.
"""

from .connector_base import ConnectorBase, ConnectorStatus
from .connector_registry import connector_registry

__all__ = ['ConnectorBase', 'ConnectorStatus', 'connector_registry']

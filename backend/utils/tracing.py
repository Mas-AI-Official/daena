"""
Distributed Tracing with OpenTelemetry for Daena AI System.

This module provides tracing instrumentation for:
- FastAPI requests/responses
- Message Bus V2 operations
- Council rounds (Scout/Debate/Commit)
- NBMF memory operations
- LLM exchanges

Tracing is optional and can be disabled via environment variable.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry (optional dependency)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp")


class TracingService:
    """Service for managing distributed tracing."""
    
    def __init__(self, enabled: bool = True, service_name: str = "daena-ai", endpoint: Optional[str] = None):
        self.enabled = enabled and OPENTELEMETRY_AVAILABLE
        self.service_name = service_name
        self.endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        
        if not self.enabled:
            logger.info("Tracing disabled")
            return
        
        try:
            # Create resource
            resource = Resource.create({
                "service.name": service_name,
                "service.version": "2.0.0",
            })
            
            # Create tracer provider
            provider = TracerProvider(resource=resource)
            
            # Add exporters
            if self.endpoint:
                # OTLP exporter (for Jaeger, Tempo, etc.)
                otlp_exporter = OTLPSpanExporter(endpoint=self.endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"Tracing enabled with OTLP exporter: {self.endpoint}")
            else:
                # Console exporter (for development)
                console_exporter = ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(console_exporter))
                logger.info("Tracing enabled with console exporter")
            
            # Set global tracer provider
            trace.set_tracer_provider(provider)
            
            self.tracer = trace.get_tracer(service_name)
            logger.info("Tracing service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            self.enabled = False
    
    def get_tracer(self):
        """Get the tracer instance."""
        if not self.enabled:
            return None
        return self.tracer
    
    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Create a span context manager."""
        if not self.enabled or not self.tracer:
            yield None
            return
        
        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the current span."""
        if not self.enabled:
            return
        
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(name, attributes or {})
    
    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the current span."""
        if not self.enabled:
            return
        
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(key, str(value))
    
    def set_status(self, status_code: str, description: Optional[str] = None):
        """Set status on the current span."""
        if not self.enabled:
            return
        
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            if status_code == "ok":
                current_span.set_status(Status(StatusCode.OK))
            elif status_code == "error":
                current_span.set_status(Status(StatusCode.ERROR, description or ""))


# Global tracing service instance
_tracing_service: Optional[TracingService] = None


def init_tracing(enabled: bool = True, service_name: str = "daena-ai", endpoint: Optional[str] = None):
    """Initialize the global tracing service."""
    global _tracing_service
    _tracing_service = TracingService(enabled=enabled, service_name=service_name, endpoint=endpoint)
    return _tracing_service


def get_tracing_service() -> Optional[TracingService]:
    """Get the global tracing service."""
    return _tracing_service


def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry."""
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry not available, skipping FastAPI instrumentation")
        return
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


# Convenience functions for common operations
def trace_message_bus(operation: str, topic: str, message_id: str):
    """Trace a message bus operation."""
    service = get_tracing_service()
    if service:
        service.set_attribute("message_bus.operation", operation)
        service.set_attribute("message_bus.topic", topic)
        service.set_attribute("message_bus.message_id", message_id)


def trace_council_round(department: str, phase: str, round_id: str):
    """Trace a council round operation."""
    service = get_tracing_service()
    if service:
        service.set_attribute("council.department", department)
        service.set_attribute("council.phase", phase)
        service.set_attribute("council.round_id", round_id)


def trace_nbmf_operation(operation: str, item_id: str, cls: str, tier: str):
    """Trace an NBMF memory operation."""
    service = get_tracing_service()
    if service:
        service.set_attribute("nbmf.operation", operation)
        service.set_attribute("nbmf.item_id", item_id)
        service.set_attribute("nbmf.class", cls)
        service.set_attribute("nbmf.tier", tier)


def trace_llm_exchange(model: str, cas_hit: bool, near_dup: bool):
    """Trace an LLM exchange operation."""
    service = get_tracing_service()
    if service:
        service.set_attribute("llm.model", model)
        service.set_attribute("llm.cas_hit", str(cas_hit))
        service.set_attribute("llm.near_dup", str(near_dup))


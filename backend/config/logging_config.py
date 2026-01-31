"""
Structured Logging Configuration for Production.

Features:
- JSON logging for production (structured logs)
- Human-readable logging for development
- Log levels per environment
- Log rotation
- Trace ID integration
"""

import os
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add trace ID if available
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class TraceContextFilter(logging.Filter):
    """
    Ensure structured-context fields exist on every LogRecord.
    Prevents formatter KeyError for missing fields like trace_id.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class SafeFormatter(logging.Formatter):
    """
    Formatter that safely handles missing fields like trace_id.
    Falls back to "-" if trace_id is not present.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Ensure trace_id exists before formatting
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        try:
            return super().format(record)
        except (KeyError, ValueError) as e:
            # If formatting still fails, use a safe fallback
            return f"{record.asctime} - {record.name} - {record.levelname} - [-] - {record.getMessage()}"


def setup_logging(environment: str = None):
    """
    Setup structured logging based on environment.
    
    Args:
        environment: Environment name ("production", "development", "test")
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Windows console safety: avoid UnicodeEncodeError (cp1252) breaking logs
    # SKIP if running in tests (pytest captures stdout, reconfiguring breaks it)
    if environment != "test":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.filters.clear()
    root_logger.addFilter(TraceContextFilter())
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Use JSON formatter for production, standard for development
    if environment == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format for development - use SafeFormatter to handle missing trace_id
        formatter = SafeFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        console_handler.addFilter(TraceContextFilter())
    
    root_logger.addHandler(console_handler)
    
    # Add file handler with rotation for production
    if environment == "production":
        log_dir = os.getenv("LOG_DIR", "./logs")
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, "daena.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(TraceContextFilter())
        root_logger.addHandler(file_handler)
    
    # Set root logger level
    root_logger.setLevel(log_level)
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured for {environment} environment (level: {log_level})")


# NOTE: Do not auto-run setup_logging() on import.
# FastAPI/Uvicorn imports modules in subprocess reloaders; auto-configuring logging
# here can crash startup (e.g., missing trace_id fields) and can double-install handlers.


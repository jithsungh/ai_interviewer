"""
Structured Logging

Provides JSON-formatted logging with automatic context injection.
Supports request ID correlation, user/tenant context, and event tracking.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional, Dict


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Converts log records to JSON with consistent schema:
    - timestamp (ISO 8601 with timezone)
    - level (INFO, WARNING, ERROR, etc.)
    - logger (module name)
    - message (log message)
    - request_id (optional, from record.request_id)
    - connection_id (optional, from record.connection_id)
    - user_id (optional, from record.user_id)
    - submission_id (optional, from record.submission_id)
    - organization_id (optional, from record.organization_id)
    - event_type (optional, from record.event_type)
    - latency_ms (optional, from record.latency_ms)
    - metadata (optional, from record.metadata)
    - exception (optional, from record.exc_info)
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: LogRecord to format
            
        Returns:
            JSON-formatted log entry as string
        """
        # Base fields
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Add correlation fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "connection_id"):
            log_entry["connection_id"] = record.connection_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        if hasattr(record, "submission_id"):
            log_entry["submission_id"] = record.submission_id

        if hasattr(record, "organization_id"):
            log_entry["organization_id"] = record.organization_id

        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type

        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms

        # Add metadata if present
        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ContextLogger:
    """
    Logger with automatic context injection.
    
    Wraps a standard logger and automatically injects context fields
    (request_id, user_id, etc.) into all log entries.
    
    Usage:
        logger = ContextLogger(
            logger=logging.getLogger("app"),
            request_id="req_abc123",
            user_id=42,
            organization_id=1
        )
        
        logger.info(
            "Exchange created",
            event_type="exchange_created",
            latency_ms=45,
            metadata={"exchange_id": 123}
        )
    """

    def __init__(
        self,
        logger: logging.Logger,
        request_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        user_id: Optional[int] = None,
        submission_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ):
        """
        Initialize context logger.
        
        Args:
            logger: Base logger to wrap
            request_id: HTTP request ID
            connection_id: WebSocket/WebRTC connection ID
            user_id: User ID
            submission_id: Interview submission ID
            organization_id: Organization/tenant ID
        """
        self.logger = logger
        self.request_id = request_id
        self.connection_id = connection_id
        self.user_id = user_id
        self.submission_id = submission_id
        self.organization_id = organization_id

    def _log(
        self,
        level: int,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Any] = None,
        extra_fields: Optional[Dict[str, Any]] = None
    ):
        """
        Log with automatic context injection.
        
        Args:
            level: Log level (logging.INFO, logging.WARNING, etc.)
            message: Log message
            event_type: Event type classification
            latency_ms: Operation latency in milliseconds
            metadata: Additional metadata dictionary
            exc_info: Exception info (for error logging)
            extra_fields: Additional fields dict (supports callers using extra=)
        """
        extra: Dict[str, Any] = {}

        if self.request_id:
            extra["request_id"] = self.request_id
        if self.connection_id:
            extra["connection_id"] = self.connection_id
        if self.user_id:
            extra["user_id"] = self.user_id
        if self.submission_id:
            extra["submission_id"] = self.submission_id
        if self.organization_id:
            extra["organization_id"] = self.organization_id
        if event_type:
            extra["event_type"] = event_type
        if latency_ms is not None:
            extra["latency_ms"] = latency_ms
        if metadata:
            extra["metadata"] = metadata
        if extra_fields:
            # Merge caller-provided extra fields; event_type/latency_ms extracted above take precedence
            for k, v in extra_fields.items():
                if k == "event_type" and not event_type:
                    extra["event_type"] = v
                elif k == "latency_ms" and latency_ms is None:
                    extra["latency_ms"] = v
                elif k not in extra:
                    extra[k] = v

        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """Log debug message with context"""
        self._log(logging.DEBUG, message, event_type, latency_ms, metadata, extra_fields=extra)

    def info(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """Log info message with context"""
        self._log(logging.INFO, message, event_type, latency_ms, metadata, extra_fields=extra)

    def warning(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """Log warning message with context"""
        self._log(logging.WARNING, message, event_type, latency_ms, metadata, extra_fields=extra)

    def error(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Any] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """Log error message with context"""
        self._log(logging.ERROR, message, event_type, latency_ms, metadata, exc_info, extra_fields=extra)

    def critical(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Any] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        """Log critical message with context"""
        self._log(logging.CRITICAL, message, event_type, latency_ms, metadata, exc_info, extra_fields=extra)


def configure_structured_logging(
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = False,
    log_file_path: str = "/var/log/app/app.log"
) -> logging.Logger:
    """
    Configure structured JSON logging.
    
    Sets up root logger with:
    - JSON formatter
    - Console handler (optional)
    - File handler (optional)
    - Specified log level
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Enable console logging
        enable_file: Enable file logging
        log_file_path: Path to log file (if file logging enabled)
        
    Returns:
        Configured root logger
    """
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    formatter = StructuredFormatter()

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if enable_file:
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_context_logger(
    request_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    user_id: Optional[int] = None,
    submission_id: Optional[int] = None,
    organization_id: Optional[int] = None
) -> ContextLogger:
    """
    Create context-aware logger.
    
    Args:
        request_id: HTTP request ID
        connection_id: WebSocket/WebRTC connection ID
        user_id: User ID
        submission_id: Interview submission ID
        organization_id: Organization/tenant ID
        
    Returns:
        ContextLogger with injected context
    """
    logger = logging.getLogger("app")

    return ContextLogger(
        logger=logger,
        request_id=request_id,
        connection_id=connection_id,
        user_id=user_id,
        submission_id=submission_id,
        organization_id=organization_id
    )

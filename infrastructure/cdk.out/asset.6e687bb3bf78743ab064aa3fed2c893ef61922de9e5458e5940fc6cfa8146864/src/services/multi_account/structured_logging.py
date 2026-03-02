"""
Structured Logging Utility for Multi-Account Cost Management

Provides structured logging with consistent format and metadata
for all multi-account operations.
"""

import json
import logging
import time
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Context information for structured logs."""
    operation: str
    request_id: Optional[str] = None
    account_id: Optional[str] = None
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    level: str
    message: str
    context: LogContext
    metadata: Dict[str, Any]
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class StructuredLogger:
    """Structured logger for multi-account operations."""
    
    def __init__(self, name: str, context: Optional[LogContext] = None):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.context = context or LogContext(operation="unknown")
        self._start_time = None
    
    def set_context(self, context: LogContext) -> None:
        """Set logging context."""
        self.context = context
    
    def update_context(self, **kwargs) -> None:
        """Update logging context with new values."""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
    
    def start_operation(self) -> None:
        """Start timing an operation."""
        self._start_time = time.time()
    
    def _log(self, level: LogLevel, message: str, metadata: Optional[Dict[str, Any]] = None,
             error: Optional[Exception] = None) -> None:
        """Internal logging method."""
        duration_ms = None
        if self._start_time:
            duration_ms = (time.time() - self._start_time) * 1000
        
        log_entry = LogEntry(
            timestamp=datetime.now(UTC).isoformat(),
            level=level.value,
            message=message,
            context=self.context,
            metadata=metadata or {},
            duration_ms=duration_ms,
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None
        )
        
        # Convert to JSON for structured logging
        log_dict = asdict(log_entry)
        # Remove None values to keep logs clean
        log_dict = {k: v for k, v in log_dict.items() if v is not None}
        
        # Log using standard logger
        getattr(self.logger, level.value.lower())(json.dumps(log_dict))
    
    def debug(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, metadata)
    
    def info(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, metadata)
    
    def warning(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, metadata)
    
    def error(self, message: str, error: Optional[Exception] = None, 
              metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, metadata, error)
    
    def critical(self, message: str, error: Optional[Exception] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, metadata, error)
    
    def operation_start(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log operation start."""
        self.context.operation = operation
        self.start_operation()
        self.info(f"Operation started: {operation}", metadata)
    
    def operation_success(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log operation success."""
        self.info(f"Operation completed successfully: {operation}", metadata)
    
    def operation_failure(self, operation: str, error: Exception, 
                         metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log operation failure."""
        self.error(f"Operation failed: {operation}", error, metadata)
    
    def cost_collection_start(self, account_count: int, date_range: str) -> None:
        """Log cost collection start."""
        self.operation_start("cost_collection", {
            "account_count": account_count,
            "date_range": date_range
        })
    
    def cost_collection_progress(self, completed: int, total: int, failed: int) -> None:
        """Log cost collection progress."""
        self.info("Cost collection progress", {
            "completed_accounts": completed,
            "total_accounts": total,
            "failed_accounts": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0
        })
    
    def cost_collection_complete(self, successful: int, failed: int, duration_ms: float) -> None:
        """Log cost collection completion."""
        self.operation_success("cost_collection", {
            "successful_accounts": successful,
            "failed_accounts": failed,
            "total_duration_ms": duration_ms,
            "success_rate": (successful / (successful + failed) * 100) if (successful + failed) > 0 else 0
        })
    
    def api_request_start(self, endpoint: str, method: str, user_id: Optional[str] = None) -> None:
        """Log API request start."""
        self.update_context(user_id=user_id)
        self.operation_start(f"api_request_{method}_{endpoint}", {
            "endpoint": endpoint,
            "method": method
        })
    
    def api_request_complete(self, endpoint: str, status_code: int, 
                           response_size: Optional[int] = None) -> None:
        """Log API request completion."""
        self.operation_success(f"api_request", {
            "endpoint": endpoint,
            "status_code": status_code,
            "response_size_bytes": response_size
        })
    
    def cache_hit(self, cache_type: str, key: str) -> None:
        """Log cache hit."""
        self.debug("Cache hit", {
            "cache_type": cache_type,
            "cache_key": key
        })
    
    def cache_miss(self, cache_type: str, key: str) -> None:
        """Log cache miss."""
        self.debug("Cache miss", {
            "cache_type": cache_type,
            "cache_key": key
        })
    
    def allocation_complete(self, account_id: str, total_cost: float, 
                          allocated_cost: float, unallocated_cost: float) -> None:
        """Log cost allocation completion."""
        unallocated_percentage = (unallocated_cost / total_cost * 100) if total_cost > 0 else 0
        
        self.info("Cost allocation completed", {
            "account_id": account_id,
            "total_cost": total_cost,
            "allocated_cost": allocated_cost,
            "unallocated_cost": unallocated_cost,
            "unallocated_percentage": unallocated_percentage
        })


def get_logger(name: str, context: Optional[LogContext] = None) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name, context)


def create_context(operation: str, **kwargs) -> LogContext:
    """Create a log context with the given operation and optional fields."""
    return LogContext(operation=operation, **kwargs)


# Configure root logger for JSON output
def configure_structured_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(message)s',  # Just the message since we're using JSON
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Disable boto3 debug logging
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
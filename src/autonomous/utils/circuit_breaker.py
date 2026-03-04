"""
Circuit Breaker Pattern

Implements circuit breaker pattern to prevent cascading failures and provide
graceful degradation when services are unavailable.

Requirements: 10.7, 10.8
"""
import time
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional
from datetime import datetime, timedelta

import boto3


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation with three states: CLOSED, OPEN, HALF_OPEN.
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, requests fail fast without calling service
    - HALF_OPEN: Testing recovery, limited requests allowed
    
    Requirements: 10.7, 10.8
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 1,
        event_bus_name: Optional[str] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name for identification
            failure_threshold: Number of failures before opening circuit (default: 5)
            timeout_seconds: Seconds to wait before attempting recovery (default: 60)
            half_open_max_calls: Max calls allowed in half-open state (default: 1)
            event_bus_name: EventBridge bus name for emitting events (optional)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self.event_bus_name = event_bus_name
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.half_open_calls = 0
        
        # AWS clients
        self.events_client = boto3.client("events") if event_bus_name else None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Result of function execution
        
        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Will retry after {self._time_until_retry():.0f}s"
                )
        
        # Check if we're in HALF_OPEN and exceeded max calls
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is HALF_OPEN and max calls exceeded"
                )
            self.half_open_calls += 1
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Successful call in HALF_OPEN state, close circuit
            self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self, exception: Exception):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        print(f"Circuit breaker '{self.name}' failure {self.failure_count}/{self.failure_threshold}: {exception}")
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN state, reopen circuit
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            # Check if we should open circuit
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.opened_at is None:
            return False
        
        elapsed = time.time() - self.opened_at
        return elapsed >= self.timeout_seconds
    
    def _time_until_retry(self) -> float:
        """Calculate time until retry attempt."""
        if self.opened_at is None:
            return 0.0
        
        elapsed = time.time() - self.opened_at
        return max(0.0, self.timeout_seconds - elapsed)
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        self.half_open_calls = 0
        
        print(f"Circuit breaker '{self.name}' transitioned to OPEN")
        
        # Emit CloudWatch Event
        self._emit_state_change_event()
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        
        print(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
        
        # Emit CloudWatch Event
        self._emit_state_change_event()
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        self.half_open_calls = 0
        
        print(f"Circuit breaker '{self.name}' transitioned to CLOSED")
        
        # Emit CloudWatch Event
        self._emit_state_change_event()
    
    def _emit_state_change_event(self):
        """Emit state change event to EventBridge."""
        if not self.events_client or not self.event_bus_name:
            return
        
        try:
            self.events_client.put_events(
                Entries=[{
                    'Source': 'costguard.autonomous.circuitbreaker',
                    'DetailType': 'CircuitBreakerStateChange',
                    'Detail': {
                        'circuit_breaker_name': self.name,
                        'state': self.state.value,
                        'failure_count': self.failure_count,
                        'success_count': self.success_count,
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    'EventBusName': self.event_bus_name
                }]
            )
        except Exception as e:
            print(f"Failed to emit circuit breaker event: {e}")
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        self._transition_to_closed()
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'timeout_seconds': self.timeout_seconds,
            'opened_at': self.opened_at,
            'time_until_retry': self._time_until_retry() if self.state == CircuitState.OPEN else 0
        }


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    event_bus_name: Optional[str] = None
) -> Callable:
    """
    Decorator for wrapping functions with circuit breaker.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening
        timeout_seconds: Seconds to wait before retry
        event_bus_name: EventBridge bus name for events
    
    Returns:
        Decorated function with circuit breaker
    
    Example:
        @circuit_breaker(name="api_service", failure_threshold=3)
        def call_api():
            # Make API call
            pass
    
    Requirements: 10.7, 10.8
    """
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds,
        event_bus_name=event_bus_name
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Global circuit breaker registry
_circuit_breakers = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    event_bus_name: Optional[str] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening
        timeout_seconds: Seconds to wait before retry
        event_bus_name: EventBridge bus name for events
    
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            event_bus_name=event_bus_name
        )
    
    return _circuit_breakers[name]


def reset_all_circuit_breakers():
    """Reset all circuit breakers to CLOSED state."""
    for breaker in _circuit_breakers.values():
        breaker.reset()


def get_all_circuit_breaker_stats() -> list:
    """Get statistics for all circuit breakers."""
    return [breaker.get_stats() for breaker in _circuit_breakers.values()]

"""
Rate limiting utilities for API calls.

This module provides rate limiting functionality to ensure API usage stays within
limits and costs are controlled while maintaining system performance.
"""

import time
import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    requests_per_minute: int
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    burst_size: Optional[int] = None
    
    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = min(10, self.requests_per_minute // 2)


@dataclass
class RateLimitState:
    """State tracking for rate limiting."""
    
    minute_requests: deque = field(default_factory=deque)
    hour_requests: deque = field(default_factory=deque)
    day_requests: deque = field(default_factory=deque)
    last_request_time: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """
    Thread-safe rate limiter for API calls.
    
    Supports per-minute, per-hour, and per-day limits with burst handling.
    """
    
    def __init__(self):
        self._limits: Dict[str, RateLimitConfig] = {}
        self._states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def configure(self, service: str, config: RateLimitConfig) -> None:
        """Configure rate limits for a service."""
        self._limits[service] = config
        logger.info(f"Configured rate limits for {service}: {config.requests_per_minute}/min")
    
    def can_make_request(self, service: str) -> bool:
        """Check if a request can be made without violating rate limits."""
        if service not in self._limits:
            return True
        
        config = self._limits[service]
        state = self._states[service]
        current_time = time.time()
        
        with state.lock:
            # Clean old requests
            self._clean_old_requests(state, current_time)
            
            # Check minute limit
            if len(state.minute_requests) >= config.requests_per_minute:
                return False
            
            # Check hour limit
            if config.requests_per_hour and len(state.hour_requests) >= config.requests_per_hour:
                return False
            
            # Check day limit
            if config.requests_per_day and len(state.day_requests) >= config.requests_per_day:
                return False
            
            return True
    
    def wait_time(self, service: str) -> float:
        """Get the time to wait before the next request can be made."""
        if service not in self._limits:
            return 0.0
        
        config = self._limits[service]
        state = self._states[service]
        current_time = time.time()
        
        with state.lock:
            self._clean_old_requests(state, current_time)
            
            wait_times = []
            
            # Check minute limit
            if len(state.minute_requests) >= config.requests_per_minute:
                oldest_request = state.minute_requests[0]
                wait_times.append(60.0 - (current_time - oldest_request))
            
            # Check hour limit
            if config.requests_per_hour and len(state.hour_requests) >= config.requests_per_hour:
                oldest_request = state.hour_requests[0]
                wait_times.append(3600.0 - (current_time - oldest_request))
            
            # Check day limit
            if config.requests_per_day and len(state.day_requests) >= config.requests_per_day:
                oldest_request = state.day_requests[0]
                wait_times.append(86400.0 - (current_time - oldest_request))
            
            return max(wait_times) if wait_times else 0.0
    
    def record_request(self, service: str) -> None:
        """Record that a request was made."""
        if service not in self._limits:
            return
        
        state = self._states[service]
        current_time = time.time()
        
        with state.lock:
            state.minute_requests.append(current_time)
            state.hour_requests.append(current_time)
            state.day_requests.append(current_time)
            state.last_request_time = current_time
            
            # Clean old requests
            self._clean_old_requests(state, current_time)
    
    def _clean_old_requests(self, state: RateLimitState, current_time: float) -> None:
        """Remove old requests from tracking queues."""
        # Clean minute requests (older than 60 seconds)
        while state.minute_requests and current_time - state.minute_requests[0] > 60:
            state.minute_requests.popleft()
        
        # Clean hour requests (older than 3600 seconds)
        while state.hour_requests and current_time - state.hour_requests[0] > 3600:
            state.hour_requests.popleft()
        
        # Clean day requests (older than 86400 seconds)
        while state.day_requests and current_time - state.day_requests[0] > 86400:
            state.day_requests.popleft()
    
    async def wait_for_slot(self, service: str) -> None:
        """Wait until a request slot is available."""
        wait_time = self.wait_time(service)
        if wait_time > 0:
            logger.info(f"Rate limit reached for {service}, waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)


def rate_limited(service: str, limiter: Optional[RateLimiter] = None):
    """
    Decorator to apply rate limiting to functions.
    
    Args:
        service: Name of the service for rate limiting
        limiter: RateLimiter instance (uses global if None)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal limiter
            if limiter is None:
                limiter = get_global_rate_limiter()
            
            await limiter.wait_for_slot(service)
            try:
                result = await func(*args, **kwargs)
                limiter.record_request(service)
                return result
            except Exception as e:
                # Still record the request even if it failed
                limiter.record_request(service)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal limiter
            if limiter is None:
                limiter = get_global_rate_limiter()
            
            # For sync functions, we can't wait, so we just check
            if not limiter.can_make_request(service):
                wait_time = limiter.wait_time(service)
                raise Exception(f"Rate limit exceeded for {service}. Wait {wait_time:.2f} seconds.")
            
            try:
                result = func(*args, **kwargs)
                limiter.record_request(service)
                return result
            except Exception as e:
                limiter.record_request(service)
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_global_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


def configure_global_rate_limits(limits: Dict[str, RateLimitConfig]) -> None:
    """Configure rate limits for the global rate limiter."""
    limiter = get_global_rate_limiter()
    for service, config in limits.items():
        limiter.configure(service, config)
"""
Caching utilities for API responses and processed data.

This module provides intelligent caching to reduce API calls, improve performance,
and ensure system reliability when APIs are unavailable.
"""

import json
import pickle
import hashlib
import time
from typing import Any, Optional, Dict, Union, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from functools import wraps
import logging
import diskcache as dc

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached entry with metadata."""
    
    data: Any
    timestamp: float
    expiry_time: float
    source: str
    size_bytes: int
    access_count: int = 0
    last_access: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() > self.expiry_time
    
    def is_fresh(self, max_age_seconds: float) -> bool:
        """Check if the cache entry is fresh enough."""
        return (time.time() - self.timestamp) < max_age_seconds
    
    def record_access(self) -> None:
        """Record that this entry was accessed."""
        self.access_count += 1
        self.last_access = time.time()


class SmartCache:
    """
    Intelligent caching system with TTL, size limits, and LRU eviction.
    
    Features:
    - Time-based expiration
    - Size-based eviction
    - Access frequency tracking
    - Serialization support for complex objects
    """
    
    def __init__(
        self,
        cache_dir: Union[str, Path],
        max_size_mb: int = 1000,
        default_ttl_hours: int = 24,
        cleanup_interval_hours: int = 6
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_hours * 3600
        self.cleanup_interval_seconds = cleanup_interval_hours * 3600
        
        # Use diskcache for persistent storage
        self._cache = dc.Cache(str(self.cache_dir))
        self._last_cleanup = time.time()
        
        logger.info(f"Initialized cache at {self.cache_dir} with {max_size_mb}MB limit")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        try:
            entry_data = self._cache.get(key)
            if entry_data is None:
                return default
            
            entry = pickle.loads(entry_data)
            
            if entry.is_expired():
                self._cache.delete(key)
                logger.debug(f"Cache entry expired: {key}")
                return default
            
            entry.record_access()
            self._cache.set(key, pickle.dumps(entry))
            
            logger.debug(f"Cache hit: {key}")
            return entry.data
            
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return default
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[int] = None,
        source: str = "unknown"
    ) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_hours: Time to live in hours (uses default if None)
            source: Source of the data (for tracking)
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            ttl_seconds = (ttl_hours * 3600) if ttl_hours else self.default_ttl_seconds
            current_time = time.time()
            
            # Serialize the value to calculate size
            serialized_value = pickle.dumps(value)
            size_bytes = len(serialized_value)
            
            entry = CacheEntry(
                data=value,
                timestamp=current_time,
                expiry_time=current_time + ttl_seconds,
                source=source,
                size_bytes=size_bytes
            )
            
            # Check if we need to make space
            self._ensure_space(size_bytes)
            
            # Store the entry
            self._cache.set(key, pickle.dumps(entry))
            
            logger.debug(f"Cache set: {key} ({size_bytes} bytes, TTL: {ttl_hours}h)")
            
            # Periodic cleanup
            if current_time - self._last_cleanup > self.cleanup_interval_seconds:
                self._cleanup_expired()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        try:
            return self._cache.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            self._cache.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            total_size = 0
            entry_count = 0
            expired_count = 0
            sources = {}
            
            current_time = time.time()
            
            for key in self._cache:
                try:
                    entry_data = self._cache.get(key)
                    if entry_data:
                        entry = pickle.loads(entry_data)
                        entry_count += 1
                        total_size += entry.size_bytes
                        
                        if entry.is_expired():
                            expired_count += 1
                        
                        sources[entry.source] = sources.get(entry.source, 0) + 1
                        
                except Exception:
                    continue
            
            return {
                'total_entries': entry_count,
                'total_size_mb': total_size / (1024 * 1024),
                'expired_entries': expired_count,
                'sources': sources,
                'cache_dir': str(self.cache_dir),
                'max_size_mb': self.max_size_bytes / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure there's enough space for a new entry."""
        current_size = self._get_current_size()
        
        if current_size + required_bytes > self.max_size_bytes:
            # Need to free up space
            bytes_to_free = (current_size + required_bytes) - self.max_size_bytes
            self._evict_lru(bytes_to_free)
    
    def _get_current_size(self) -> int:
        """Get the current cache size in bytes."""
        total_size = 0
        for key in self._cache:
            try:
                entry_data = self._cache.get(key)
                if entry_data:
                    entry = pickle.loads(entry_data)
                    total_size += entry.size_bytes
            except Exception:
                continue
        return total_size
    
    def _evict_lru(self, bytes_to_free: int) -> None:
        """Evict least recently used entries to free space."""
        entries_with_keys = []
        
        for key in self._cache:
            try:
                entry_data = self._cache.get(key)
                if entry_data:
                    entry = pickle.loads(entry_data)
                    entries_with_keys.append((key, entry))
            except Exception:
                continue
        
        # Sort by last access time (oldest first)
        entries_with_keys.sort(key=lambda x: x[1].last_access)
        
        freed_bytes = 0
        for key, entry in entries_with_keys:
            if freed_bytes >= bytes_to_free:
                break
            
            self._cache.delete(key)
            freed_bytes += entry.size_bytes
            logger.debug(f"Evicted cache entry: {key} ({entry.size_bytes} bytes)")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        current_time = time.time()
        expired_keys = []
        
        for key in self._cache:
            try:
                entry_data = self._cache.get(key)
                if entry_data:
                    entry = pickle.loads(entry_data)
                    if entry.is_expired():
                        expired_keys.append(key)
            except Exception:
                expired_keys.append(key)  # Remove corrupted entries
        
        for key in expired_keys:
            self._cache.delete(key)
        
        self._last_cleanup = current_time
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


def cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        SHA256 hash of the arguments
    """
    # Create a stable representation of the arguments
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    
    # Serialize and hash
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.sha256(key_str.encode()).hexdigest()


def cached(
    cache_instance: Optional[SmartCache] = None,
    ttl_hours: int = 24,
    key_prefix: str = ""
):
    """
    Decorator to cache function results.
    
    Args:
        cache_instance: Cache instance to use (uses global if None)
        ttl_hours: Time to live in hours
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal cache_instance
            if cache_instance is None:
                cache_instance = get_global_cache()
            
            # Generate cache key
            func_key = f"{key_prefix}{func.__name__}_{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = cache_instance.get(func_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_instance.set(
                func_key,
                result,
                ttl_hours=ttl_hours,
                source=f"function:{func.__name__}"
            )
            
            return result
        
        return wrapper
    return decorator


# Global cache instance
_global_cache: Optional[SmartCache] = None


def get_global_cache() -> SmartCache:
    """Get the global cache instance."""
    global _global_cache
    if _global_cache is None:
        from ..config.settings import config
        _global_cache = SmartCache(
            cache_dir=config.cache.cache_directory,
            max_size_mb=config.cache.max_cache_size_mb,
            default_ttl_hours=config.cache.cache_expiry_hours
        )
    return _global_cache
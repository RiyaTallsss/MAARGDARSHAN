"""
Smart caching system to reduce API dependency and improve UI responsiveness.

This module provides intelligent caching with predictive prefetching, adaptive TTL,
and cache warming strategies to minimize API calls and improve response times.
"""

import asyncio
import time
import hashlib
import pickle
import json
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from pathlib import Path
import threading
from collections import defaultdict, OrderedDict
import weakref
import gzip
import statistics

from .cache import get_global_cache

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache strategy types."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"  # Adaptive based on usage patterns


class CachePriority(Enum):
    """Cache entry priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    prefetch_count: int = 0
    prefetch_hit_count: int = 0
    total_size_bytes: int = 0
    average_access_time_ms: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hit_count + self.miss_count
        return (self.hit_count / total) if total > 0 else 0.0
    
    @property
    def prefetch_efficiency(self) -> float:
        """Calculate prefetch efficiency."""
        return (self.prefetch_hit_count / self.prefetch_count) if self.prefetch_count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': self.hit_rate,
            'eviction_count': self.eviction_count,
            'prefetch_count': self.prefetch_count,
            'prefetch_hit_count': self.prefetch_hit_count,
            'prefetch_efficiency': self.prefetch_efficiency,
            'total_size_bytes': self.total_size_bytes,
            'average_access_time_ms': self.average_access_time_ms
        }


@dataclass
class CacheEntry:
    """Smart cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: Optional[float]
    priority: CachePriority
    size_bytes: int
    source: str  # API source that generated this data
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    compression_enabled: bool = False
    prefetched: bool = False
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl_seconds is None:
            return False
        
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def freshness_score(self) -> float:
        """Calculate freshness score (0-1, higher is fresher)."""
        if self.ttl_seconds is None:
            return 1.0
        
        age_ratio = self.age_seconds / self.ttl_seconds
        return max(0.0, 1.0 - age_ratio)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'ttl_seconds': self.ttl_seconds,
            'priority': self.priority.value,
            'size_bytes': self.size_bytes,
            'source': self.source,
            'dependencies': self.dependencies,
            'tags': self.tags,
            'compression_enabled': self.compression_enabled,
            'prefetched': self.prefetched,
            'is_expired': self.is_expired,
            'age_seconds': self.age_seconds,
            'freshness_score': self.freshness_score
        }


class PredictiveModel:
    """Simple predictive model for cache prefetching."""
    
    def __init__(self):
        self.access_patterns: Dict[str, List[datetime]] = defaultdict(list)
        self.key_relationships: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.temporal_patterns: Dict[str, List[float]] = defaultdict(list)  # Hour of day patterns
    
    def record_access(self, key: str, timestamp: Optional[datetime] = None) -> None:
        """Record cache key access for pattern learning."""
        timestamp = timestamp or datetime.now()
        
        # Record access time
        self.access_patterns[key].append(timestamp)
        
        # Keep only recent accesses (last 7 days)
        cutoff = timestamp - timedelta(days=7)
        self.access_patterns[key] = [
            ts for ts in self.access_patterns[key] if ts > cutoff
        ]
        
        # Record temporal pattern (hour of day)
        hour = timestamp.hour
        self.temporal_patterns[key].append(hour)
        
        # Keep only recent temporal data
        if len(self.temporal_patterns[key]) > 100:
            self.temporal_patterns[key] = self.temporal_patterns[key][-100:]
    
    def record_key_relationship(self, key1: str, key2: str) -> None:
        """Record relationship between cache keys."""
        self.key_relationships[key1][key2] += 1
        self.key_relationships[key2][key1] += 1
    
    def predict_next_accesses(self, current_key: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Predict next likely cache accesses."""
        predictions = []
        
        # Relationship-based predictions
        if current_key in self.key_relationships:
            for related_key, count in self.key_relationships[current_key].items():
                confidence = min(count / 10.0, 1.0)  # Normalize to 0-1
                predictions.append((related_key, confidence))
        
        # Temporal pattern predictions
        current_hour = datetime.now().hour
        for key, hours in self.temporal_patterns.items():
            if key != current_key and hours:
                # Calculate how often this key is accessed at current hour
                hour_matches = sum(1 for h in hours if abs(h - current_hour) <= 1)
                confidence = hour_matches / len(hours)
                
                if confidence > 0.1:  # Only include if >10% chance
                    predictions.append((key, confidence * 0.5))  # Lower weight for temporal
        
        # Sort by confidence and return top predictions
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions[:limit]
    
    def should_prefetch(self, key: str) -> bool:
        """Determine if a key should be prefetched."""
        if key not in self.access_patterns:
            return False
        
        accesses = self.access_patterns[key]
        if len(accesses) < 3:  # Need some history
            return False
        
        # Check access frequency
        recent_accesses = [
            ts for ts in accesses 
            if ts > datetime.now() - timedelta(hours=24)
        ]
        
        # Prefetch if accessed multiple times in last 24 hours
        return len(recent_accesses) >= 2


class SmartCache:
    """
    Smart caching system with predictive prefetching and adaptive strategies.
    
    Features:
    - Multiple eviction strategies (LRU, LFU, TTL, Adaptive)
    - Predictive prefetching based on access patterns
    - Adaptive TTL based on data freshness and usage
    - Cache warming for critical data
    - Compression for large entries
    - Dependency tracking and invalidation
    - Performance metrics and optimization
    """
    
    def __init__(self, 
                 max_size_mb: int = 100,
                 strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
                 enable_compression: bool = True,
                 enable_prefetching: bool = True):
        
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.strategy = strategy
        self.enable_compression = enable_compression
        self.enable_prefetching = enable_prefetching
        
        # Cache storage
        self.entries: Dict[str, CacheEntry] = {}
        self.access_order: OrderedDict = OrderedDict()  # For LRU
        self.access_frequency: Dict[str, int] = defaultdict(int)  # For LFU
        
        # Predictive model
        self.predictive_model = PredictiveModel()
        
        # Metrics
        self.metrics = CacheMetrics()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._prefetch_task: Optional[asyncio.Task] = None
        self._active = False
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"Smart cache initialized: {max_size_mb}MB, strategy={strategy.value}")
    
    async def start(self) -> None:
        """Start background cache management tasks."""
        if self._active:
            return
        
        self._active = True
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Start prefetch task if enabled
        if self.enable_prefetching:
            self._prefetch_task = asyncio.create_task(self._prefetch_loop())
        
        logger.info("Smart cache background tasks started")
    
    async def stop(self) -> None:
        """Stop background cache management tasks."""
        if not self._active:
            return
        
        self._active = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._prefetch_task:
            self._prefetch_task.cancel()
            try:
                await self._prefetch_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Smart cache background tasks stopped")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with smart access tracking."""
        with self._lock:
            start_time = time.time()
            
            if key not in self.entries:
                self.metrics.miss_count += 1
                self._update_access_time(start_time)
                return default
            
            entry = self.entries[key]
            
            # Check if expired
            if entry.is_expired:
                self._remove_entry(key)
                self.metrics.miss_count += 1
                self._update_access_time(start_time)
                return default
            
            # Update access metadata
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            
            # Update access tracking
            self.access_order.move_to_end(key)
            self.access_frequency[key] += 1
            
            # Record access for predictive model
            self.predictive_model.record_access(key)
            
            # Update metrics
            self.metrics.hit_count += 1
            if entry.prefetched:
                self.metrics.prefetch_hit_count += 1
            
            self._update_access_time(start_time)
            
            # Decompress if needed
            value = self._decompress_value(entry.value) if entry.compression_enabled else entry.value
            
            return value
    
    def set(self, 
            key: str, 
            value: Any, 
            ttl_seconds: Optional[float] = None,
            priority: CachePriority = CachePriority.NORMAL,
            source: str = "unknown",
            tags: List[str] = None,
            dependencies: List[str] = None) -> None:
        """Set value in cache with smart metadata."""
        
        with self._lock:
            # Calculate size
            size_bytes = self._calculate_size(value)
            
            # Compress if enabled and beneficial
            compressed_value = value
            compression_enabled = False
            
            if self.enable_compression and size_bytes > 1024:  # Compress if >1KB
                try:
                    compressed = self._compress_value(value)
                    if len(compressed) < size_bytes * 0.8:  # Only if >20% reduction
                        compressed_value = compressed
                        compression_enabled = True
                        size_bytes = len(compressed)
                except Exception as e:
                    logger.debug(f"Compression failed for {key}: {e}")
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=compressed_value,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=1,
                ttl_seconds=ttl_seconds,
                priority=priority,
                size_bytes=size_bytes,
                source=source,
                dependencies=dependencies or [],
                tags=tags or [],
                compression_enabled=compression_enabled
            )
            
            # Check if we need to make space
            self._ensure_space(size_bytes)
            
            # Add to cache
            if key in self.entries:
                # Update existing entry
                old_entry = self.entries[key]
                self.metrics.total_size_bytes -= old_entry.size_bytes
            
            self.entries[key] = entry
            self.access_order[key] = True
            self.access_frequency[key] += 1
            
            # Update metrics
            self.metrics.total_size_bytes += size_bytes
            
            # Record access for predictive model
            self.predictive_model.record_access(key)
            
            logger.debug(f"Cached {key}: {size_bytes} bytes, TTL={ttl_seconds}s")
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        with self._lock:
            if key not in self.entries:
                return False
            
            self._remove_entry(key)
            return True
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        with self._lock:
            keys_to_remove = [
                key for key, entry in self.entries.items()
                if tag in entry.tags
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            logger.info(f"Invalidated {len(keys_to_remove)} entries with tag '{tag}'")
            return len(keys_to_remove)
    
    def invalidate_by_dependency(self, dependency: str) -> int:
        """Invalidate all entries that depend on a specific key."""
        with self._lock:
            keys_to_remove = [
                key for key, entry in self.entries.items()
                if dependency in entry.dependencies
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            logger.info(f"Invalidated {len(keys_to_remove)} entries depending on '{dependency}'")
            return len(keys_to_remove)
    
    def warm_cache(self, warm_functions: List[Callable[[], Tuple[str, Any, Optional[float]]]]) -> None:
        """Warm cache with critical data."""
        logger.info(f"Warming cache with {len(warm_functions)} functions")
        
        for warm_func in warm_functions:
            try:
                key, value, ttl = warm_func()
                self.set(key, value, ttl_seconds=ttl, priority=CachePriority.HIGH, source="cache_warming")
            except Exception as e:
                logger.warning(f"Cache warming failed for function: {e}")
    
    async def prefetch_related(self, current_key: str) -> int:
        """Prefetch related cache entries based on predictions."""
        if not self.enable_prefetching:
            return 0
        
        predictions = self.predictive_model.predict_next_accesses(current_key)
        prefetched_count = 0
        
        for predicted_key, confidence in predictions:
            if predicted_key not in self.entries and confidence > 0.3:
                # Try to prefetch this key
                success = await self._attempt_prefetch(predicted_key)
                if success:
                    prefetched_count += 1
                    self.metrics.prefetch_count += 1
        
        return prefetched_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        with self._lock:
            return self.metrics.to_dict()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information."""
        with self._lock:
            return {
                'total_entries': len(self.entries),
                'total_size_bytes': self.metrics.total_size_bytes,
                'max_size_bytes': self.max_size_bytes,
                'utilization_percent': (self.metrics.total_size_bytes / self.max_size_bytes) * 100,
                'strategy': self.strategy.value,
                'compression_enabled': self.enable_compression,
                'prefetching_enabled': self.enable_prefetching,
                'metrics': self.metrics.to_dict(),
                'top_accessed_keys': self._get_top_accessed_keys(10)
            }
    
    def optimize_ttl(self, key: str) -> Optional[float]:
        """Calculate optimal TTL for a cache key based on usage patterns."""
        if key not in self.entries:
            return None
        
        entry = self.entries[key]
        
        # Base TTL on data source and access patterns
        base_ttl = self._get_base_ttl_for_source(entry.source)
        
        # Adjust based on access frequency
        if entry.access_count > 10:
            # Frequently accessed data should have longer TTL
            base_ttl *= 1.5
        elif entry.access_count < 3:
            # Rarely accessed data should have shorter TTL
            base_ttl *= 0.7
        
        # Adjust based on priority
        if entry.priority == CachePriority.CRITICAL:
            base_ttl *= 2.0
        elif entry.priority == CachePriority.LOW:
            base_ttl *= 0.5
        
        return base_ttl
    
    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure enough space in cache by evicting entries if needed."""
        while (self.metrics.total_size_bytes + required_bytes) > self.max_size_bytes:
            if not self.entries:
                break
            
            # Select entry to evict based on strategy
            key_to_evict = self._select_eviction_candidate()
            if key_to_evict:
                self._remove_entry(key_to_evict)
                self.metrics.eviction_count += 1
            else:
                break
    
    def _select_eviction_candidate(self) -> Optional[str]:
        """Select cache entry for eviction based on strategy."""
        if not self.entries:
            return None
        
        if self.strategy == CacheStrategy.LRU:
            # Least Recently Used
            return next(iter(self.access_order))
        
        elif self.strategy == CacheStrategy.LFU:
            # Least Frequently Used
            return min(self.entries.keys(), key=lambda k: self.access_frequency[k])
        
        elif self.strategy == CacheStrategy.TTL:
            # Shortest TTL or oldest
            return min(
                self.entries.keys(),
                key=lambda k: (
                    self.entries[k].ttl_seconds or float('inf'),
                    self.entries[k].created_at
                )
            )
        
        else:  # ADAPTIVE
            # Adaptive strategy considering multiple factors
            scores = {}
            
            for key, entry in self.entries.items():
                score = 0.0
                
                # Age factor (older = higher eviction score)
                age_hours = entry.age_seconds / 3600
                score += age_hours * 0.3
                
                # Access frequency factor (less frequent = higher eviction score)
                freq_score = 1.0 / max(entry.access_count, 1)
                score += freq_score * 0.3
                
                # Priority factor (lower priority = higher eviction score)
                priority_score = (5 - entry.priority.value) * 0.2
                score += priority_score
                
                # Size factor (larger = higher eviction score)
                size_score = entry.size_bytes / (1024 * 1024)  # MB
                score += size_score * 0.1
                
                # Freshness factor (stale = higher eviction score)
                freshness_score = 1.0 - entry.freshness_score
                score += freshness_score * 0.1
                
                scores[key] = score
            
            return max(scores.keys(), key=lambda k: scores[k])
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry from cache and update tracking."""
        if key not in self.entries:
            return
        
        entry = self.entries[key]
        
        # Update metrics
        self.metrics.total_size_bytes -= entry.size_bytes
        
        # Remove from tracking
        del self.entries[key]
        self.access_order.pop(key, None)
        self.access_frequency.pop(key, None)
        
        logger.debug(f"Removed cache entry: {key}")
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of a value in bytes."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            # Fallback estimation
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return 8
            elif isinstance(value, (list, tuple)):
                return sum(self._calculate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    self._calculate_size(k) + self._calculate_size(v)
                    for k, v in value.items()
                )
            else:
                return 1024  # Default estimate
    
    def _compress_value(self, value: Any) -> bytes:
        """Compress a value using gzip."""
        pickled = pickle.dumps(value)
        return gzip.compress(pickled)
    
    def _decompress_value(self, compressed_value: bytes) -> Any:
        """Decompress a value using gzip."""
        decompressed = gzip.decompress(compressed_value)
        return pickle.loads(decompressed)
    
    def _update_access_time(self, start_time: float) -> None:
        """Update average access time metric."""
        access_time_ms = (time.time() - start_time) * 1000
        
        # Update running average
        total_accesses = self.metrics.hit_count + self.metrics.miss_count
        if total_accesses > 0:
            self.metrics.average_access_time_ms = (
                (self.metrics.average_access_time_ms * (total_accesses - 1) + access_time_ms) /
                total_accesses
            )
    
    def _get_base_ttl_for_source(self, source: str) -> float:
        """Get base TTL for different data sources."""
        ttl_mapping = {
            'nasa_srtm': 86400,      # 24 hours - elevation data is stable
            'openweathermap': 3600,  # 1 hour - weather data changes frequently
            'overpass': 21600,       # 6 hours - OSM data changes moderately
            'local_dem': 604800,     # 1 week - local DEM is very stable
            'local_csv': 43200,      # 12 hours - local weather data
            'cache_warming': 7200,   # 2 hours - warmed cache data
            'unknown': 3600          # 1 hour - default
        }
        
        return ttl_mapping.get(source, 3600)
    
    def _get_top_accessed_keys(self, limit: int) -> List[Dict[str, Any]]:
        """Get top accessed cache keys."""
        sorted_keys = sorted(
            self.entries.keys(),
            key=lambda k: self.entries[k].access_count,
            reverse=True
        )
        
        return [
            {
                'key': key,
                'access_count': self.entries[key].access_count,
                'size_bytes': self.entries[key].size_bytes,
                'age_seconds': self.entries[key].age_seconds,
                'source': self.entries[key].source
            }
            for key in sorted_keys[:limit]
        ]
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while self._active:
            try:
                await self._cleanup_expired_entries()
                await asyncio.sleep(60)  # Run every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_expired_entries(self) -> None:
        """Remove expired entries from cache."""
        with self._lock:
            expired_keys = [
                key for key, entry in self.entries.items()
                if entry.is_expired
            ]
            
            for key in expired_keys:
                self._remove_entry(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def _prefetch_loop(self) -> None:
        """Background prefetching loop."""
        while self._active:
            try:
                await self._run_prefetch_cycle()
                await asyncio.sleep(300)  # Run every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache prefetch error: {e}")
                await asyncio.sleep(300)
    
    async def _run_prefetch_cycle(self) -> None:
        """Run a prefetch cycle for likely-to-be-accessed data."""
        # Find keys that should be prefetched
        prefetch_candidates = []
        
        with self._lock:
            for key in self.entries.keys():
                if self.predictive_model.should_prefetch(key):
                    predictions = self.predictive_model.predict_next_accesses(key, limit=3)
                    for predicted_key, confidence in predictions:
                        if predicted_key not in self.entries and confidence > 0.4:
                            prefetch_candidates.append((predicted_key, confidence))
        
        # Sort by confidence and prefetch top candidates
        prefetch_candidates.sort(key=lambda x: x[1], reverse=True)
        
        for key, confidence in prefetch_candidates[:5]:  # Limit to 5 prefetches per cycle
            success = await self._attempt_prefetch(key)
            if success:
                self.metrics.prefetch_count += 1
    
    async def _attempt_prefetch(self, key: str) -> bool:
        """Attempt to prefetch a cache key."""
        # This would integrate with the actual data fetching system
        # For now, just log the attempt
        logger.debug(f"Would prefetch cache key: {key}")
        return False  # Placeholder


# Global smart cache instance
_smart_cache: Optional[SmartCache] = None


def get_smart_cache() -> SmartCache:
    """Get the global smart cache instance."""
    global _smart_cache
    if _smart_cache is None:
        _smart_cache = SmartCache()
    return _smart_cache


def smart_cached(ttl_seconds: Optional[float] = None,
                priority: CachePriority = CachePriority.NORMAL,
                tags: List[str] = None,
                enable_prefetch: bool = True):
    """
    Decorator for smart caching of function results.
    
    Args:
        ttl_seconds: Time to live for cached result
        priority: Cache priority
        tags: Cache tags for invalidation
        enable_prefetch: Enable predictive prefetching
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            cache = get_smart_cache()
            
            # Generate cache key
            key_data = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                # Prefetch related data if enabled
                if enable_prefetch:
                    asyncio.create_task(cache.prefetch_related(key))
                
                return result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            cache.set(
                key=key,
                value=result,
                ttl_seconds=ttl_seconds,
                priority=priority,
                source=func.__name__,
                tags=tags or []
            )
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            cache = get_smart_cache()
            
            # Generate cache key
            key_data = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(
                key=key,
                value=result,
                ttl_seconds=ttl_seconds,
                priority=priority,
                source=func.__name__,
                tags=tags or []
            )
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
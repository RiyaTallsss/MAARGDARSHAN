"""
Performance monitoring and API optimization module.

This module provides comprehensive performance monitoring, API cost tracking,
and optimization recommendations for the rural infrastructure planning system.
"""

import asyncio
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import json
import statistics
from pathlib import Path
import psutil
import gc

from ..config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for system monitoring."""
    timestamp: datetime
    response_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    api_calls_count: int
    cache_hit_rate: float
    error_count: int
    concurrent_users: int
    data_processing_time_ms: float
    route_generation_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'response_time_ms': self.response_time_ms,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'api_calls_count': self.api_calls_count,
            'cache_hit_rate': self.cache_hit_rate,
            'error_count': self.error_count,
            'concurrent_users': self.concurrent_users,
            'data_processing_time_ms': self.data_processing_time_ms,
            'route_generation_time_ms': self.route_generation_time_ms
        }


@dataclass
class APILatencyMetrics:
    """API-specific latency and performance metrics."""
    api_name: str
    request_count: int = 0
    total_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0.0
    error_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    last_request_time: Optional[datetime] = None
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_request(self, response_time_ms: float, success: bool = True, 
                   timeout: bool = False, rate_limited: bool = False) -> None:
        """Add a request measurement."""
        self.request_count += 1
        self.last_request_time = datetime.now()
        
        if success:
            self.total_response_time_ms += response_time_ms
            self.min_response_time_ms = min(self.min_response_time_ms, response_time_ms)
            self.max_response_time_ms = max(self.max_response_time_ms, response_time_ms)
            self.response_times.append(response_time_ms)
        else:
            self.error_count += 1
            if timeout:
                self.timeout_count += 1
            if rate_limited:
                self.rate_limit_count += 1
    
    def get_average_response_time(self) -> float:
        """Get average response time for successful requests."""
        successful_requests = self.request_count - self.error_count
        if successful_requests > 0:
            return self.total_response_time_ms / successful_requests
        return 0.0
    
    def get_percentile_response_time(self, percentile: float) -> float:
        """Get percentile response time."""
        if not self.response_times:
            return 0.0
        
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.request_count == 0:
            return 100.0
        return ((self.request_count - self.error_count) / self.request_count) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'api_name': self.api_name,
            'request_count': self.request_count,
            'average_response_time_ms': self.get_average_response_time(),
            'min_response_time_ms': self.min_response_time_ms if self.min_response_time_ms != float('inf') else 0,
            'max_response_time_ms': self.max_response_time_ms,
            'p50_response_time_ms': self.get_percentile_response_time(50),
            'p95_response_time_ms': self.get_percentile_response_time(95),
            'p99_response_time_ms': self.get_percentile_response_time(99),
            'success_rate_percent': self.get_success_rate(),
            'error_count': self.error_count,
            'timeout_count': self.timeout_count,
            'rate_limit_count': self.rate_limit_count,
            'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None
        }


@dataclass
class CostTrackingMetrics:
    """Cost tracking and optimization metrics."""
    total_cost_today: float = 0.0
    cost_by_api: Dict[str, float] = field(default_factory=dict)
    requests_by_api: Dict[str, int] = field(default_factory=dict)
    cache_savings: float = 0.0
    optimization_savings: float = 0.0
    projected_monthly_cost: float = 0.0
    cost_alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_api_cost(self, api_name: str, cost: float) -> None:
        """Add cost for an API request."""
        self.total_cost_today += cost
        self.cost_by_api[api_name] = self.cost_by_api.get(api_name, 0.0) + cost
        self.requests_by_api[api_name] = self.requests_by_api.get(api_name, 0) + 1
        self.projected_monthly_cost = self.total_cost_today * 30
        
        # Check for cost alerts
        self._check_cost_alerts(api_name, cost)
    
    def add_cache_savings(self, api_name: str, saved_cost: float) -> None:
        """Add savings from cache hit."""
        self.cache_savings += saved_cost
    
    def add_optimization_savings(self, saved_cost: float, reason: str) -> None:
        """Add savings from optimization."""
        self.optimization_savings += saved_cost
    
    def _check_cost_alerts(self, api_name: str, cost: float) -> None:
        """Check if cost thresholds are exceeded."""
        # Daily cost alert
        if self.total_cost_today > 10.0 and len([a for a in self.cost_alerts if a['type'] == 'daily_limit']) == 0:
            self.cost_alerts.append({
                'type': 'daily_limit',
                'message': f'Daily cost exceeded $10: ${self.total_cost_today:.2f}',
                'timestamp': datetime.now().isoformat(),
                'severity': 'warning'
            })
        
        # API-specific cost alert
        api_cost = self.cost_by_api.get(api_name, 0.0)
        if api_cost > 5.0 and len([a for a in self.cost_alerts if a['api'] == api_name]) == 0:
            self.cost_alerts.append({
                'type': 'api_cost',
                'api': api_name,
                'message': f'{api_name} cost exceeded $5: ${api_cost:.2f}',
                'timestamp': datetime.now().isoformat(),
                'severity': 'warning'
            })
    
    def get_cost_efficiency_score(self) -> float:
        """Calculate cost efficiency score (0-1)."""
        if self.total_cost_today == 0:
            return 1.0
        
        # Higher cache savings = higher efficiency
        cache_efficiency = min(1.0, self.cache_savings / max(0.01, self.total_cost_today))
        
        # Lower cost per request = higher efficiency
        total_requests = sum(self.requests_by_api.values())
        if total_requests > 0:
            avg_cost_per_request = self.total_cost_today / total_requests
            cost_efficiency = max(0.0, 1.0 - (avg_cost_per_request / 0.1))  # $0.1 as expensive threshold
        else:
            cost_efficiency = 1.0
        
        return (cache_efficiency + cost_efficiency) / 2
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_cost_today': round(self.total_cost_today, 4),
            'projected_monthly_cost': round(self.projected_monthly_cost, 2),
            'cost_by_api': {k: round(v, 4) for k, v in self.cost_by_api.items()},
            'requests_by_api': self.requests_by_api,
            'cache_savings': round(self.cache_savings, 4),
            'optimization_savings': round(self.optimization_savings, 4),
            'cost_efficiency_score': round(self.get_cost_efficiency_score(), 3),
            'cost_alerts': self.cost_alerts
        }


class PerformanceMonitor:
    """
    Comprehensive performance monitoring and optimization system.
    
    Features:
    - Real-time performance metrics collection
    - API latency and cost tracking
    - Memory and CPU usage monitoring
    - Concurrent user session management
    - Performance optimization recommendations
    - Automated alerting for performance issues
    """
    
    def __init__(self):
        self.metrics_history: deque = deque(maxlen=1000)  # Keep last 1000 measurements
        self.api_metrics: Dict[str, APILatencyMetrics] = {}
        self.cost_metrics = CostTrackingMetrics()
        self.active_sessions: Dict[str, datetime] = {}
        self.performance_alerts: List[Dict[str, Any]] = []
        
        # Performance thresholds
        self.response_time_threshold_ms = 5000  # 5 seconds
        self.memory_threshold_mb = 1024  # 1GB
        self.cpu_threshold_percent = 80
        self.error_rate_threshold_percent = 5
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Performance optimization state
        self._optimization_recommendations: List[Dict[str, Any]] = []
        self._last_optimization_check = datetime.now()
        
        logger.info("Performance monitor initialized")
    
    def start_monitoring(self, interval_seconds: int = 30) -> None:
        """Start continuous performance monitoring."""
        if self._monitoring_active:
            logger.warning("Performance monitoring already active")
            return
        
        self._monitoring_active = True
        self._stop_monitoring.clear()
        
        def monitoring_loop():
            while not self._stop_monitoring.wait(interval_seconds):
                try:
                    self._collect_system_metrics()
                    self._check_performance_alerts()
                    self._update_optimization_recommendations()
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
        
        self._monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        logger.info(f"Performance monitoring started with {interval_seconds}s interval")
    
    def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        self._stop_monitoring.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        
        logger.info("Performance monitoring stopped")
    
    def _collect_system_metrics(self) -> None:
        """Collect current system performance metrics."""
        try:
            # Get system metrics
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Calculate cache hit rate
            cache_hit_rate = self._calculate_cache_hit_rate()
            
            # Count active sessions (sessions active in last 5 minutes)
            now = datetime.now()
            active_cutoff = now - timedelta(minutes=5)
            concurrent_users = len([s for s in self.active_sessions.values() if s > active_cutoff])
            
            # Create metrics snapshot
            metrics = PerformanceMetrics(
                timestamp=now,
                response_time_ms=self._get_average_response_time(),
                memory_usage_mb=memory_info.used / (1024 * 1024),
                cpu_usage_percent=cpu_percent,
                api_calls_count=sum(m.request_count for m in self.api_metrics.values()),
                cache_hit_rate=cache_hit_rate,
                error_count=sum(m.error_count for m in self.api_metrics.values()),
                concurrent_users=concurrent_users,
                data_processing_time_ms=self._get_average_processing_time(),
                route_generation_time_ms=self._get_average_route_generation_time()
            )
            
            self.metrics_history.append(metrics)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        # This would integrate with the actual cache system
        # For now, return a placeholder value
        return 0.75  # 75% hit rate
    
    def _get_average_response_time(self) -> float:
        """Get average response time across all APIs."""
        if not self.api_metrics:
            return 0.0
        
        total_time = sum(m.get_average_response_time() for m in self.api_metrics.values())
        return total_time / len(self.api_metrics)
    
    def _get_average_processing_time(self) -> float:
        """Get average data processing time."""
        # This would be measured during actual data processing
        # For now, return a placeholder value
        return 150.0  # 150ms average
    
    def _get_average_route_generation_time(self) -> float:
        """Get average route generation time."""
        # This would be measured during route generation
        # For now, return a placeholder value
        return 800.0  # 800ms average
    
    def track_api_request(self, api_name: str, response_time_ms: float, 
                         success: bool = True, timeout: bool = False, 
                         rate_limited: bool = False, cost: float = 0.0) -> None:
        """Track an API request for performance monitoring."""
        # Initialize API metrics if not exists
        if api_name not in self.api_metrics:
            self.api_metrics[api_name] = APILatencyMetrics(api_name=api_name)
        
        # Record the request
        self.api_metrics[api_name].add_request(
            response_time_ms=response_time_ms,
            success=success,
            timeout=timeout,
            rate_limited=rate_limited
        )
        
        # Track cost if applicable
        if cost > 0:
            self.cost_metrics.add_api_cost(api_name, cost)
        
        # Check for immediate alerts
        self._check_immediate_alerts(api_name, response_time_ms, success)
    
    def track_cache_hit(self, api_name: str, saved_cost: float = 0.0) -> None:
        """Track a cache hit for performance monitoring."""
        if saved_cost > 0:
            self.cost_metrics.add_cache_savings(api_name, saved_cost)
    
    def track_user_session(self, session_id: str) -> None:
        """Track a user session for concurrent user monitoring."""
        self.active_sessions[session_id] = datetime.now()
        
        # Clean up old sessions (older than 1 hour)
        cutoff = datetime.now() - timedelta(hours=1)
        self.active_sessions = {
            sid: timestamp for sid, timestamp in self.active_sessions.items()
            if timestamp > cutoff
        }
    
    def _check_immediate_alerts(self, api_name: str, response_time_ms: float, success: bool) -> None:
        """Check for immediate performance alerts."""
        now = datetime.now()
        
        # Response time alert
        if response_time_ms > self.response_time_threshold_ms:
            self.performance_alerts.append({
                'type': 'slow_response',
                'api_name': api_name,
                'response_time_ms': response_time_ms,
                'threshold_ms': self.response_time_threshold_ms,
                'message': f'{api_name} slow response: {response_time_ms:.0f}ms > {self.response_time_threshold_ms}ms',
                'timestamp': now.isoformat(),
                'severity': 'warning'
            })
        
        # Error rate alert
        if not success:
            api_metrics = self.api_metrics[api_name]
            error_rate = (api_metrics.error_count / api_metrics.request_count) * 100
            
            if error_rate > self.error_rate_threshold_percent:
                self.performance_alerts.append({
                    'type': 'high_error_rate',
                    'api_name': api_name,
                    'error_rate_percent': error_rate,
                    'threshold_percent': self.error_rate_threshold_percent,
                    'message': f'{api_name} high error rate: {error_rate:.1f}% > {self.error_rate_threshold_percent}%',
                    'timestamp': now.isoformat(),
                    'severity': 'error'
                })
    
    def _check_performance_alerts(self) -> None:
        """Check for system-wide performance alerts."""
        if not self.metrics_history:
            return
        
        latest_metrics = self.metrics_history[-1]
        now = datetime.now()
        
        # Memory usage alert
        if latest_metrics.memory_usage_mb > self.memory_threshold_mb:
            self.performance_alerts.append({
                'type': 'high_memory_usage',
                'memory_usage_mb': latest_metrics.memory_usage_mb,
                'threshold_mb': self.memory_threshold_mb,
                'message': f'High memory usage: {latest_metrics.memory_usage_mb:.0f}MB > {self.memory_threshold_mb}MB',
                'timestamp': now.isoformat(),
                'severity': 'warning'
            })
        
        # CPU usage alert
        if latest_metrics.cpu_usage_percent > self.cpu_threshold_percent:
            self.performance_alerts.append({
                'type': 'high_cpu_usage',
                'cpu_usage_percent': latest_metrics.cpu_usage_percent,
                'threshold_percent': self.cpu_threshold_percent,
                'message': f'High CPU usage: {latest_metrics.cpu_usage_percent:.1f}% > {self.cpu_threshold_percent}%',
                'timestamp': now.isoformat(),
                'severity': 'warning'
            })
        
        # Clean up old alerts (keep only last 24 hours)
        cutoff = now - timedelta(hours=24)
        self.performance_alerts = [
            alert for alert in self.performance_alerts
            if datetime.fromisoformat(alert['timestamp']) > cutoff
        ]
    
    def _update_optimization_recommendations(self) -> None:
        """Update performance optimization recommendations."""
        now = datetime.now()
        
        # Only update recommendations every 5 minutes
        if (now - self._last_optimization_check).total_seconds() < 300:
            return
        
        self._last_optimization_check = now
        self._optimization_recommendations.clear()
        
        # Analyze API performance
        for api_name, metrics in self.api_metrics.items():
            avg_response_time = metrics.get_average_response_time()
            success_rate = metrics.get_success_rate()
            
            # Slow API recommendation
            if avg_response_time > 3000:  # > 3 seconds
                self._optimization_recommendations.append({
                    'type': 'api_optimization',
                    'priority': 'high',
                    'api_name': api_name,
                    'issue': f'Slow average response time: {avg_response_time:.0f}ms',
                    'recommendations': [
                        'Implement request caching with longer TTL',
                        'Use regional API endpoints if available',
                        'Consider request batching',
                        'Implement circuit breaker pattern'
                    ]
                })
            
            # Low success rate recommendation
            if success_rate < 95:
                self._optimization_recommendations.append({
                    'type': 'reliability_optimization',
                    'priority': 'high',
                    'api_name': api_name,
                    'issue': f'Low success rate: {success_rate:.1f}%',
                    'recommendations': [
                        'Implement exponential backoff retry logic',
                        'Add fallback data sources',
                        'Monitor API service status',
                        'Implement request queuing for rate-limited APIs'
                    ]
                })
        
        # Analyze system performance
        if len(self.metrics_history) >= 10:
            recent_metrics = list(self.metrics_history)[-10:]
            
            # High memory usage trend
            avg_memory = statistics.mean(m.memory_usage_mb for m in recent_metrics)
            if avg_memory > self.memory_threshold_mb * 0.8:
                self._optimization_recommendations.append({
                    'type': 'memory_optimization',
                    'priority': 'medium',
                    'issue': f'High memory usage trend: {avg_memory:.0f}MB',
                    'recommendations': [
                        'Implement data streaming for large datasets',
                        'Optimize cache size and eviction policies',
                        'Use memory-efficient data structures',
                        'Implement garbage collection tuning'
                    ]
                })
            
            # High CPU usage trend
            avg_cpu = statistics.mean(m.cpu_usage_percent for m in recent_metrics)
            if avg_cpu > self.cpu_threshold_percent * 0.8:
                self._optimization_recommendations.append({
                    'type': 'cpu_optimization',
                    'priority': 'medium',
                    'issue': f'High CPU usage trend: {avg_cpu:.1f}%',
                    'recommendations': [
                        'Implement asynchronous processing for heavy operations',
                        'Use worker processes for CPU-intensive tasks',
                        'Optimize algorithms and data processing',
                        'Consider horizontal scaling'
                    ]
                })
        
        # Cost optimization recommendations
        if self.cost_metrics.total_cost_today > 5.0:  # > $5/day
            efficiency_score = self.cost_metrics.get_cost_efficiency_score()
            
            if efficiency_score < 0.7:
                self._optimization_recommendations.append({
                    'type': 'cost_optimization',
                    'priority': 'high',
                    'issue': f'High daily cost with low efficiency: ${self.cost_metrics.total_cost_today:.2f}',
                    'recommendations': [
                        'Increase cache TTL for expensive APIs',
                        'Implement intelligent API source selection',
                        'Use free APIs during non-critical hours',
                        'Batch requests to reduce API calls'
                    ]
                })
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        now = datetime.now()
        
        # Calculate performance trends
        trends = self._calculate_performance_trends()
        
        # Get current system status
        current_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        # API performance summary
        api_summary = {}
        for api_name, metrics in self.api_metrics.items():
            api_summary[api_name] = metrics.to_dict()
        
        # System health assessment
        health_score = self._calculate_system_health_score()
        
        return {
            'timestamp': now.isoformat(),
            'system_health': {
                'overall_score': health_score,
                'status': self._get_health_status(health_score),
                'current_metrics': current_metrics.to_dict() if current_metrics else None
            },
            'api_performance': api_summary,
            'cost_tracking': self.cost_metrics.to_dict(),
            'performance_trends': trends,
            'active_alerts': self.performance_alerts[-10:],  # Last 10 alerts
            'optimization_recommendations': self._optimization_recommendations,
            'concurrent_users': len([
                s for s in self.active_sessions.values()
                if s > now - timedelta(minutes=5)
            ]),
            'monitoring_status': {
                'active': self._monitoring_active,
                'metrics_collected': len(self.metrics_history),
                'apis_tracked': len(self.api_metrics)
            }
        }
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        if len(self.metrics_history) < 2:
            return {'status': 'insufficient_data'}
        
        # Get recent metrics (last hour)
        now = datetime.now()
        recent_cutoff = now - timedelta(hours=1)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > recent_cutoff
        ]
        
        if len(recent_metrics) < 2:
            return {'status': 'insufficient_recent_data'}
        
        # Calculate trends
        response_times = [m.response_time_ms for m in recent_metrics]
        memory_usage = [m.memory_usage_mb for m in recent_metrics]
        cpu_usage = [m.cpu_usage_percent for m in recent_metrics]
        
        return {
            'status': 'available',
            'response_time': {
                'trend': self._calculate_trend(response_times),
                'average': statistics.mean(response_times),
                'min': min(response_times),
                'max': max(response_times)
            },
            'memory_usage': {
                'trend': self._calculate_trend(memory_usage),
                'average': statistics.mean(memory_usage),
                'min': min(memory_usage),
                'max': max(memory_usage)
            },
            'cpu_usage': {
                'trend': self._calculate_trend(cpu_usage),
                'average': statistics.mean(cpu_usage),
                'min': min(cpu_usage),
                'max': max(cpu_usage)
            }
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values."""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        change_percent = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
        
        if change_percent > 10:
            return 'increasing'
        elif change_percent < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_system_health_score(self) -> float:
        """Calculate overall system health score (0-100)."""
        if not self.metrics_history:
            return 50.0  # Neutral score with no data
        
        latest_metrics = self.metrics_history[-1]
        score = 100.0
        
        # Response time impact (0-30 points)
        if latest_metrics.response_time_ms > self.response_time_threshold_ms:
            score -= 30
        elif latest_metrics.response_time_ms > self.response_time_threshold_ms * 0.7:
            score -= 15
        
        # Memory usage impact (0-20 points)
        memory_ratio = latest_metrics.memory_usage_mb / self.memory_threshold_mb
        if memory_ratio > 1.0:
            score -= 20
        elif memory_ratio > 0.8:
            score -= 10
        
        # CPU usage impact (0-20 points)
        cpu_ratio = latest_metrics.cpu_usage_percent / self.cpu_threshold_percent
        if cpu_ratio > 1.0:
            score -= 20
        elif cpu_ratio > 0.8:
            score -= 10
        
        # Error rate impact (0-20 points)
        total_requests = sum(m.request_count for m in self.api_metrics.values())
        total_errors = sum(m.error_count for m in self.api_metrics.values())
        
        if total_requests > 0:
            error_rate = (total_errors / total_requests) * 100
            if error_rate > self.error_rate_threshold_percent:
                score -= 20
            elif error_rate > self.error_rate_threshold_percent * 0.5:
                score -= 10
        
        # Cache performance impact (0-10 points)
        if latest_metrics.cache_hit_rate < 0.5:
            score -= 10
        elif latest_metrics.cache_hit_rate < 0.7:
            score -= 5
        
        return max(0.0, min(100.0, score))
    
    def _get_health_status(self, health_score: float) -> str:
        """Get health status string from score."""
        if health_score >= 90:
            return 'excellent'
        elif health_score >= 75:
            return 'good'
        elif health_score >= 60:
            return 'fair'
        elif health_score >= 40:
            return 'poor'
        else:
            return 'critical'
    
    def optimize_api_usage(self) -> Dict[str, Any]:
        """Perform API usage optimization analysis."""
        optimization_results = {
            'timestamp': datetime.now().isoformat(),
            'optimizations_applied': [],
            'recommendations': [],
            'potential_savings': {
                'cost_savings_usd': 0.0,
                'performance_improvement_percent': 0.0,
                'reliability_improvement_percent': 0.0
            }
        }
        
        # Analyze each API for optimization opportunities
        for api_name, metrics in self.api_metrics.items():
            api_optimizations = self._analyze_api_optimization(api_name, metrics)
            optimization_results['recommendations'].extend(api_optimizations)
        
        # System-wide optimizations
        system_optimizations = self._analyze_system_optimization()
        optimization_results['recommendations'].extend(system_optimizations)
        
        # Calculate potential savings
        optimization_results['potential_savings'] = self._calculate_optimization_savings()
        
        return optimization_results
    
    def _analyze_api_optimization(self, api_name: str, metrics: APILatencyMetrics) -> List[Dict[str, Any]]:
        """Analyze optimization opportunities for a specific API."""
        recommendations = []
        
        avg_response_time = metrics.get_average_response_time()
        success_rate = metrics.get_success_rate()
        
        # Response time optimization
        if avg_response_time > 2000:  # > 2 seconds
            recommendations.append({
                'type': 'response_time_optimization',
                'api_name': api_name,
                'priority': 'high' if avg_response_time > 5000 else 'medium',
                'current_avg_ms': avg_response_time,
                'target_improvement': '50% reduction',
                'actions': [
                    'Implement aggressive caching (TTL: 1-6 hours)',
                    'Use connection pooling and keep-alive',
                    'Implement request compression',
                    'Consider API endpoint optimization'
                ]
            })
        
        # Reliability optimization
        if success_rate < 98:
            recommendations.append({
                'type': 'reliability_optimization',
                'api_name': api_name,
                'priority': 'high' if success_rate < 95 else 'medium',
                'current_success_rate': success_rate,
                'target_improvement': '99%+ success rate',
                'actions': [
                    'Implement circuit breaker with exponential backoff',
                    'Add health check endpoints',
                    'Implement request retry with jitter',
                    'Set up monitoring and alerting'
                ]
            })
        
        # Rate limiting optimization
        if metrics.rate_limit_count > 0:
            recommendations.append({
                'type': 'rate_limit_optimization',
                'api_name': api_name,
                'priority': 'medium',
                'rate_limit_hits': metrics.rate_limit_count,
                'actions': [
                    'Implement intelligent request queuing',
                    'Use multiple API keys for load distribution',
                    'Implement request prioritization',
                    'Add rate limit prediction and throttling'
                ]
            })
        
        return recommendations
    
    def _analyze_system_optimization(self) -> List[Dict[str, Any]]:
        """Analyze system-wide optimization opportunities."""
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        # Memory optimization
        recent_memory = [m.memory_usage_mb for m in list(self.metrics_history)[-10:]]
        avg_memory = statistics.mean(recent_memory) if recent_memory else 0
        
        if avg_memory > self.memory_threshold_mb * 0.8:
            recommendations.append({
                'type': 'memory_optimization',
                'priority': 'high' if avg_memory > self.memory_threshold_mb else 'medium',
                'current_usage_mb': avg_memory,
                'target_improvement': '30% reduction',
                'actions': [
                    'Implement streaming data processing',
                    'Optimize cache eviction policies',
                    'Use memory-mapped files for large datasets',
                    'Implement data compression'
                ]
            })
        
        # Concurrent user optimization
        max_concurrent = max(m.concurrent_users for m in self.metrics_history)
        if max_concurrent > 50:  # High concurrency
            recommendations.append({
                'type': 'concurrency_optimization',
                'priority': 'medium',
                'max_concurrent_users': max_concurrent,
                'actions': [
                    'Implement connection pooling',
                    'Use async/await for I/O operations',
                    'Implement request queuing and load balancing',
                    'Consider horizontal scaling'
                ]
            })
        
        return recommendations
    
    def _calculate_optimization_savings(self) -> Dict[str, float]:
        """Calculate potential savings from optimizations."""
        # Cost savings from better caching
        current_cost = self.cost_metrics.total_cost_today
        cache_hit_rate = self._calculate_cache_hit_rate()
        
        # Estimate 30% cost savings from improved caching
        potential_cache_savings = current_cost * 0.3 * (1.0 - cache_hit_rate)
        
        # Performance improvement from optimizations
        # Estimate 40% improvement in response times
        performance_improvement = 40.0
        
        # Reliability improvement from better error handling
        # Estimate 5% improvement in success rates
        reliability_improvement = 5.0
        
        return {
            'cost_savings_usd': round(potential_cache_savings, 4),
            'performance_improvement_percent': performance_improvement,
            'reliability_improvement_percent': reliability_improvement
        }
    
    def export_metrics(self, filepath: Optional[Path] = None) -> Path:
        """Export performance metrics to JSON file."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = Path(f'performance_metrics_{timestamp}.json')
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'performance_report': self.get_performance_report(),
            'raw_metrics': [m.to_dict() for m in self.metrics_history],
            'api_metrics': {name: metrics.to_dict() for name, metrics in self.api_metrics.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Performance metrics exported to {filepath}")
        return filepath
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        self.metrics_history.clear()
        self.api_metrics.clear()
        self.cost_metrics = CostTrackingMetrics()
        self.active_sessions.clear()
        self.performance_alerts.clear()
        self._optimization_recommendations.clear()
        
        logger.info("Performance metrics reset")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def performance_tracked(api_name: str, cost_per_request: float = 0.0):
    """
    Decorator to automatically track API performance.
    
    Args:
        api_name: Name of the API being tracked
        cost_per_request: Cost per API request in USD
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            timeout = False
            rate_limited = False
            
            try:
                result = await func(*args, **kwargs)
                return result
            except asyncio.TimeoutError:
                success = False
                timeout = True
                raise
            except Exception as e:
                success = False
                if 'rate limit' in str(e).lower() or '429' in str(e):
                    rate_limited = True
                raise
            finally:
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                monitor.track_api_request(
                    api_name=api_name,
                    response_time_ms=response_time_ms,
                    success=success,
                    timeout=timeout,
                    rate_limited=rate_limited,
                    cost=cost_per_request if success else 0.0
                )
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            timeout = False
            rate_limited = False
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                if 'timeout' in str(e).lower():
                    timeout = True
                if 'rate limit' in str(e).lower() or '429' in str(e):
                    rate_limited = True
                raise
            finally:
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                monitor.track_api_request(
                    api_name=api_name,
                    response_time_ms=response_time_ms,
                    success=success,
                    timeout=timeout,
                    rate_limited=rate_limited,
                    cost=cost_per_request if success else 0.0
                )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
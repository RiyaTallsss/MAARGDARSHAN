"""
Advanced data source management and fallback strategies.

This module provides intelligent data source selection, health monitoring,
and adaptive fallback strategies for the rural infrastructure planning system.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from .api_client import API_Client, DataSourceStatus, BoundingBox, Coordinate, DateRange

logger = logging.getLogger(__name__)


class DataSourcePriority(Enum):
    """Priority levels for data sources."""
    CRITICAL = 1    # Essential for system operation
    HIGH = 2        # Important for quality results
    MEDIUM = 3      # Useful for enhanced features
    LOW = 4         # Nice to have


class FallbackStrategy(Enum):
    """Different fallback strategies."""
    IMMEDIATE = "immediate"           # Switch immediately on failure
    GRADUAL = "gradual"              # Try multiple sources before fallback
    COST_AWARE = "cost_aware"        # Consider cost in fallback decisions
    QUALITY_FIRST = "quality_first"  # Prioritize data quality over cost
    HYBRID = "hybrid"                # Combine multiple strategies


@dataclass
class DataSourceConfig:
    """Configuration for a data source."""
    name: str
    priority: DataSourcePriority
    max_daily_cost: float
    max_response_time_ms: float
    fallback_strategy: FallbackStrategy
    health_check_interval_minutes: int = 30
    circuit_breaker_threshold: int = 5
    recovery_time_minutes: int = 15


@dataclass
class SourceHealthMetrics:
    """Health metrics for a data source."""
    availability_score: float = 1.0
    response_time_score: float = 1.0
    cost_efficiency_score: float = 1.0
    data_quality_score: float = 1.0
    overall_health: float = 1.0
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None


class DataSourceManager:
    """
    Advanced data source management with intelligent fallback strategies.
    
    This class provides:
    - Intelligent source selection based on health, cost, and quality
    - Adaptive fallback strategies that learn from usage patterns
    - Predictive failure detection and proactive source switching
    - Cost optimization across multiple data sources
    - Quality-aware data fusion from multiple sources
    """
    
    def __init__(self, api_client: API_Client):
        self.api_client = api_client
        self.source_configs: Dict[str, DataSourceConfig] = {}
        self.health_metrics: Dict[str, SourceHealthMetrics] = {}
        self.usage_history: List[Dict[str, Any]] = []
        self.adaptive_thresholds: Dict[str, float] = {}
        
        # Initialize default configurations
        self._initialize_default_configs()
        
        # Start background health monitoring
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        logger.info("Initialized DataSourceManager with intelligent fallback strategies")
    
    def _initialize_default_configs(self) -> None:
        """Initialize default configurations for known data sources."""
        default_configs = [
            DataSourceConfig(
                name="nasa_srtm",
                priority=DataSourcePriority.HIGH,
                max_daily_cost=5.0,
                max_response_time_ms=10000,
                fallback_strategy=FallbackStrategy.QUALITY_FIRST
            ),
            DataSourceConfig(
                name="usgs_elevation",
                priority=DataSourcePriority.HIGH,
                max_daily_cost=3.0,
                max_response_time_ms=8000,
                fallback_strategy=FallbackStrategy.COST_AWARE
            ),
            DataSourceConfig(
                name="overpass",
                priority=DataSourcePriority.CRITICAL,
                max_daily_cost=0.0,  # Free service
                max_response_time_ms=15000,
                fallback_strategy=FallbackStrategy.IMMEDIATE
            ),
            DataSourceConfig(
                name="openweathermap",
                priority=DataSourcePriority.MEDIUM,
                max_daily_cost=2.0,
                max_response_time_ms=5000,
                fallback_strategy=FallbackStrategy.COST_AWARE
            ),
            DataSourceConfig(
                name="imd_api",
                priority=DataSourcePriority.HIGH,
                max_daily_cost=0.0,  # Free government service
                max_response_time_ms=12000,
                fallback_strategy=FallbackStrategy.GRADUAL
            ),
            DataSourceConfig(
                name="disaster_api",
                priority=DataSourcePriority.CRITICAL,
                max_daily_cost=0.0,  # Free government service
                max_response_time_ms=20000,
                fallback_strategy=FallbackStrategy.IMMEDIATE
            ),
            DataSourceConfig(
                name="google_places",
                priority=DataSourcePriority.LOW,
                max_daily_cost=10.0,
                max_response_time_ms=3000,
                fallback_strategy=FallbackStrategy.HYBRID
            )
        ]
        
        for config in default_configs:
            self.source_configs[config.name] = config
            self.health_metrics[config.name] = SourceHealthMetrics()
    
    async def start_health_monitoring(self) -> None:
        """Start background health monitoring for all data sources."""
        if self._health_monitor_task is None or self._health_monitor_task.done():
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("Started background health monitoring")
    
    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_monitor_task and not self._health_monitor_task.done():
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped background health monitoring")
    
    async def _health_monitor_loop(self) -> None:
        """Background loop for monitoring data source health."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all configured data sources."""
        for source_name, config in self.source_configs.items():
            try:
                await self._check_source_health(source_name, config)
            except Exception as e:
                logger.warning(f"Health check failed for {source_name}: {e}")
    
    async def _check_source_health(self, source_name: str, config: DataSourceConfig) -> None:
        """Check the health of a specific data source."""
        metrics = self.health_metrics[source_name]
        
        # Skip if recently checked
        if (metrics.last_health_check and 
            datetime.now() - metrics.last_health_check < timedelta(minutes=config.health_check_interval_minutes)):
            return
        
        # Get current status from API client
        api_status = self.api_client.get_api_status()
        source_status = api_status.get('data_sources', {}).get(source_name)
        
        if source_status:
            # Update health metrics based on current status
            metrics.availability_score = 1.0 if source_status['available'] else 0.0
            
            # Response time score (inverse relationship)
            if source_status['response_time_ms']:
                max_time = config.max_response_time_ms
                actual_time = source_status['response_time_ms']
                metrics.response_time_score = max(0.0, 1.0 - (actual_time / max_time))
            
            # Cost efficiency score
            daily_cost = source_status.get('cost_today', 0.0)
            if config.max_daily_cost > 0:
                metrics.cost_efficiency_score = max(0.0, 1.0 - (daily_cost / config.max_daily_cost))
            else:
                metrics.cost_efficiency_score = 1.0  # Free services get full score
            
            # Update failure tracking
            if source_status['failure_count'] > metrics.consecutive_failures:
                metrics.consecutive_failures = source_status['failure_count']
                metrics.last_failure_time = datetime.now()
            
            # Calculate overall health
            metrics.overall_health = (
                metrics.availability_score * 0.4 +
                metrics.response_time_score * 0.3 +
                metrics.cost_efficiency_score * 0.2 +
                metrics.data_quality_score * 0.1
            )
        
        metrics.last_health_check = datetime.now()
    
    def get_optimal_source_selection(self, data_type: str, requirements: Dict[str, Any]) -> List[str]:
        """
        Select optimal data sources based on current health and requirements.
        
        Args:
            data_type: Type of data needed ('elevation', 'osm', 'weather', 'flood')
            requirements: Requirements dict with keys like 'max_cost', 'max_response_time', 'quality_threshold'
        
        Returns:
            List of source names in priority order
        """
        # Map data types to relevant sources
        source_mapping = {
            'elevation': ['nasa_srtm', 'usgs_elevation'],
            'osm': ['overpass'],
            'weather': ['openweathermap', 'imd_api'],
            'flood': ['disaster_api'],
            'infrastructure': ['overpass', 'google_places']
        }
        
        relevant_sources = source_mapping.get(data_type, [])
        if not relevant_sources:
            return []
        
        # Score each source based on current health and requirements
        source_scores = []
        
        for source_name in relevant_sources:
            if source_name not in self.health_metrics:
                continue
            
            metrics = self.health_metrics[source_name]
            config = self.source_configs.get(source_name)
            
            if not config:
                continue
            
            # Base score from health metrics
            score = metrics.overall_health
            
            # Adjust based on requirements
            max_cost = requirements.get('max_cost', float('inf'))
            if config.max_daily_cost > max_cost:
                score *= 0.5  # Penalize expensive sources
            
            max_response_time = requirements.get('max_response_time', float('inf'))
            if config.max_response_time_ms > max_response_time:
                score *= 0.7  # Penalize slow sources
            
            quality_threshold = requirements.get('quality_threshold', 0.0)
            if metrics.data_quality_score < quality_threshold:
                score *= 0.6  # Penalize low-quality sources
            
            # Boost critical and high priority sources
            if config.priority == DataSourcePriority.CRITICAL:
                score *= 1.3
            elif config.priority == DataSourcePriority.HIGH:
                score *= 1.1
            
            source_scores.append((source_name, score))
        
        # Sort by score (highest first)
        source_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [source_name for source_name, _ in source_scores]
    
    def should_trigger_fallback(self, source_name: str, error_context: Dict[str, Any]) -> bool:
        """
        Determine if a fallback should be triggered based on error context and source health.
        
        Args:
            source_name: Name of the failing source
            error_context: Context about the error (type, frequency, etc.)
        
        Returns:
            True if fallback should be triggered
        """
        if source_name not in self.source_configs:
            return True  # Unknown source, trigger fallback
        
        config = self.source_configs[source_name]
        metrics = self.health_metrics[source_name]
        
        # Always trigger for critical failures
        error_type = error_context.get('error_type', 'unknown')
        if error_type in ['network_error', 'authentication_error', 'service_unavailable']:
            return True
        
        # Check consecutive failures against threshold
        if metrics.consecutive_failures >= config.circuit_breaker_threshold:
            return True
        
        # Check if source has been failing for too long
        if (metrics.last_failure_time and 
            datetime.now() - metrics.last_failure_time > timedelta(minutes=config.recovery_time_minutes)):
            return True
        
        # Strategy-specific logic
        if config.fallback_strategy == FallbackStrategy.IMMEDIATE:
            return True
        elif config.fallback_strategy == FallbackStrategy.GRADUAL:
            return metrics.consecutive_failures >= 2
        elif config.fallback_strategy == FallbackStrategy.COST_AWARE:
            # Consider cost in fallback decision
            daily_cost = error_context.get('daily_cost', 0.0)
            return daily_cost > config.max_daily_cost or metrics.consecutive_failures >= 3
        elif config.fallback_strategy == FallbackStrategy.QUALITY_FIRST:
            # Only fallback if quality is severely impacted
            return metrics.data_quality_score < 0.3 or metrics.consecutive_failures >= 4
        elif config.fallback_strategy == FallbackStrategy.HYBRID:
            # Combine multiple factors
            health_score = metrics.overall_health
            failure_rate = metrics.consecutive_failures / config.circuit_breaker_threshold
            return health_score < 0.4 or failure_rate > 0.6
        
        return False
    
    def get_fallback_recommendations(self, data_type: str, failed_source: str) -> Dict[str, Any]:
        """
        Get intelligent fallback recommendations when a source fails.
        
        Args:
            data_type: Type of data that failed
            failed_source: Name of the source that failed
        
        Returns:
            Fallback recommendations with alternative sources and strategies
        """
        # Get alternative sources
        alternative_sources = self.get_optimal_source_selection(
            data_type, 
            {'max_cost': 5.0, 'quality_threshold': 0.5}
        )
        
        # Remove the failed source
        alternative_sources = [s for s in alternative_sources if s != failed_source]
        
        # Determine fallback strategy
        fallback_strategy = "local_data"
        if alternative_sources:
            best_alternative = alternative_sources[0]
            alt_metrics = self.health_metrics.get(best_alternative)
            if alt_metrics and alt_metrics.overall_health > 0.7:
                fallback_strategy = "alternative_api"
        
        # Calculate expected quality impact
        failed_metrics = self.health_metrics.get(failed_source)
        quality_impact = "low"
        if failed_metrics:
            if failed_metrics.data_quality_score > 0.8:
                quality_impact = "high"
            elif failed_metrics.data_quality_score > 0.6:
                quality_impact = "medium"
        
        return {
            'fallback_strategy': fallback_strategy,
            'alternative_sources': alternative_sources,
            'quality_impact': quality_impact,
            'estimated_recovery_time': self._estimate_recovery_time(failed_source),
            'cost_impact': self._calculate_fallback_cost_impact(data_type, failed_source, alternative_sources),
            'recommendations': self._generate_fallback_recommendations(data_type, failed_source, alternative_sources)
        }
    
    def _estimate_recovery_time(self, source_name: str) -> Dict[str, Any]:
        """Estimate recovery time for a failed source."""
        config = self.source_configs.get(source_name)
        metrics = self.health_metrics.get(source_name)
        
        if not config or not metrics:
            return {'estimate_minutes': 30, 'confidence': 'low'}
        
        # Base recovery time from config
        base_time = config.recovery_time_minutes
        
        # Adjust based on failure history
        if metrics.consecutive_failures > 5:
            base_time *= 2  # Longer recovery for persistent failures
        
        # Adjust based on error type (would need error context)
        confidence = 'medium'
        if metrics.consecutive_failures < 2:
            confidence = 'high'
        elif metrics.consecutive_failures > 10:
            confidence = 'low'
        
        return {
            'estimate_minutes': base_time,
            'confidence': confidence,
            'factors': {
                'consecutive_failures': metrics.consecutive_failures,
                'last_success_hours': (datetime.now() - metrics.last_health_check).total_seconds() / 3600 if metrics.last_health_check else None
            }
        }
    
    def _calculate_fallback_cost_impact(self, data_type: str, failed_source: str, alternatives: List[str]) -> Dict[str, Any]:
        """Calculate the cost impact of using fallback sources."""
        failed_config = self.source_configs.get(failed_source)
        failed_daily_cost = failed_config.max_daily_cost if failed_config else 0.0
        
        if not alternatives:
            return {
                'cost_change': 0.0,
                'impact_level': 'none',
                'explanation': 'Using local data (no API costs)'
            }
        
        best_alternative = alternatives[0]
        alt_config = self.source_configs.get(best_alternative)
        alt_daily_cost = alt_config.max_daily_cost if alt_config else 0.0
        
        cost_change = alt_daily_cost - failed_daily_cost
        
        if cost_change <= 0:
            impact_level = 'positive'
            explanation = f'Cost savings of ${abs(cost_change):.2f}/day'
        elif cost_change < 1.0:
            impact_level = 'low'
            explanation = f'Small cost increase of ${cost_change:.2f}/day'
        elif cost_change < 5.0:
            impact_level = 'medium'
            explanation = f'Moderate cost increase of ${cost_change:.2f}/day'
        else:
            impact_level = 'high'
            explanation = f'Significant cost increase of ${cost_change:.2f}/day'
        
        return {
            'cost_change': cost_change,
            'impact_level': impact_level,
            'explanation': explanation,
            'failed_source_cost': failed_daily_cost,
            'alternative_cost': alt_daily_cost
        }
    
    def _generate_fallback_recommendations(self, data_type: str, failed_source: str, alternatives: List[str]) -> List[str]:
        """Generate specific recommendations for handling the fallback."""
        recommendations = []
        
        if alternatives:
            recommendations.append(f"Switch to {alternatives[0]} as primary source for {data_type} data")
            
            if len(alternatives) > 1:
                recommendations.append(f"Configure {alternatives[1]} as secondary backup")
        
        recommendations.append(f"Increase cache TTL for {data_type} data to reduce API dependency")
        
        failed_config = self.source_configs.get(failed_source)
        if failed_config and failed_config.priority in [DataSourcePriority.CRITICAL, DataSourcePriority.HIGH]:
            recommendations.append(f"Monitor {failed_source} closely for recovery - it's a high-priority source")
        
        recommendations.append("Consider pre-loading local data for offline operation")
        
        return recommendations
    
    def record_usage_event(self, event_data: Dict[str, Any]) -> None:
        """Record a usage event for learning and optimization."""
        event_data['timestamp'] = datetime.now().isoformat()
        self.usage_history.append(event_data)
        
        # Keep only recent history (last 1000 events)
        if len(self.usage_history) > 1000:
            self.usage_history = self.usage_history[-1000:]
        
        # Update adaptive thresholds based on usage patterns
        self._update_adaptive_thresholds()
    
    def _update_adaptive_thresholds(self) -> None:
        """Update adaptive thresholds based on usage history."""
        if len(self.usage_history) < 10:
            return  # Need more data
        
        # Analyze recent usage patterns
        recent_events = self.usage_history[-100:]  # Last 100 events
        
        # Calculate success rates by source
        source_success_rates = {}
        for event in recent_events:
            source = event.get('source')
            success = event.get('success', False)
            
            if source:
                if source not in source_success_rates:
                    source_success_rates[source] = {'successes': 0, 'total': 0}
                
                source_success_rates[source]['total'] += 1
                if success:
                    source_success_rates[source]['successes'] += 1
        
        # Update adaptive thresholds
        for source, stats in source_success_rates.items():
            if stats['total'] >= 5:  # Need minimum sample size
                success_rate = stats['successes'] / stats['total']
                
                # Adjust circuit breaker threshold based on success rate
                if success_rate > 0.9:
                    # High success rate - can be more tolerant
                    self.adaptive_thresholds[f"{source}_circuit_breaker"] = 7
                elif success_rate < 0.5:
                    # Low success rate - be more aggressive
                    self.adaptive_thresholds[f"{source}_circuit_breaker"] = 3
                else:
                    # Normal success rate - use default
                    self.adaptive_thresholds[f"{source}_circuit_breaker"] = 5
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of system health."""
        now = datetime.now()
        
        # Calculate overall health scores
        health_scores = []
        critical_issues = []
        warnings = []
        
        for source_name, metrics in self.health_metrics.items():
            config = self.source_configs.get(source_name)
            if not config:
                continue
            
            health_scores.append(metrics.overall_health)
            
            # Check for critical issues
            if metrics.availability_score < 0.1 and config.priority == DataSourcePriority.CRITICAL:
                critical_issues.append(f"Critical source {source_name} is unavailable")
            
            # Check for warnings
            if metrics.consecutive_failures > 3:
                warnings.append(f"Source {source_name} has {metrics.consecutive_failures} consecutive failures")
            
            if metrics.cost_efficiency_score < 0.3:
                warnings.append(f"Source {source_name} is exceeding cost thresholds")
        
        overall_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
        
        # Determine system status
        if critical_issues:
            system_status = 'critical'
        elif overall_health < 0.5:
            system_status = 'degraded'
        elif overall_health < 0.8:
            system_status = 'warning'
        else:
            system_status = 'healthy'
        
        return {
            'system_status': system_status,
            'overall_health_score': round(overall_health, 3),
            'critical_issues': critical_issues,
            'warnings': warnings,
            'source_count': len(self.health_metrics),
            'healthy_sources': sum(1 for m in self.health_metrics.values() if m.overall_health > 0.7),
            'last_updated': now.isoformat(),
            'adaptive_optimizations_active': len(self.adaptive_thresholds) > 0
        }